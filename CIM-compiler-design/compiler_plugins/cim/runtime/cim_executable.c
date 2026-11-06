#include "cim_executable.h"

#include <string.h>

#include "cim/Common/CIMExecutableFormat.h"
#include "iree/base/alignment.h"
#include "iree/hal/local/executable_library.h"
#include "iree/hal/local/local_executable.h"

typedef struct iree_hal_cim_view_t {
  uint8_t *data;
  uint32_t dtype;
  uint32_t rank;
  uint32_t extent[2];
  uint32_t stride[2];
} iree_hal_cim_view_t;

typedef struct iree_hal_cim_executable_t {
  iree_hal_local_executable_t base;
  const uint8_t *export_defs;
  const uint8_t *view_defs;
  const uint8_t *program_ops;
  const uint8_t *string_table;
  const uint8_t *data;
  uint8_t *array;
} iree_hal_cim_executable_t;

typedef struct iree_hal_cim_executable_loader_t {
  iree_hal_executable_loader_t base;
  iree_allocator_t host_allocator;
} iree_hal_cim_executable_loader_t;

static const iree_hal_local_executable_vtable_t iree_hal_cim_executable_vtable;
static const iree_hal_executable_loader_vtable_t
    iree_hal_cim_executable_loader_vtable;

static uint32_t iree_hal_cim_read_u32(const uint8_t *data,
                                      iree_host_size_t word_index) {
  return iree_unaligned_load_le_u32(
      (const uint32_t *)(data + word_index * sizeof(uint32_t)));
}

static int64_t iree_hal_cim_read_i64(const uint8_t *data,
                                     iree_host_size_t byte_offset) {
  return (int64_t)iree_unaligned_load_le_u64(
      (const uint64_t *)(data + byte_offset));
}

static const uint8_t *iree_hal_cim_record_at(const uint8_t *base,
                                             iree_host_size_t ordinal,
                                             uint32_t size) {
  return base + ordinal * size;
}

static iree_host_size_t iree_hal_cim_payload_size(const uint8_t *header) {
  return CIMX_HEADER_SIZE +
         CIMX_EXPORT_DEF_SIZE *
             (iree_host_size_t)iree_hal_cim_read_u32(header, 5) +
         CIMX_BUFFER_VIEW_DEF_SIZE *
             (iree_host_size_t)iree_hal_cim_read_u32(header, 6) +
         CIMX_PROGRAM_OP_DEF_SIZE *
             (iree_host_size_t)iree_hal_cim_read_u32(header, 7) +
         iree_hal_cim_read_u32(header, 8) + iree_hal_cim_read_u32(header, 9);
}

static iree_status_t
iree_hal_cim_note_view(const iree_hal_cim_executable_t *executable,
                       uint32_t ordinal, uint32_t *binding_count,
                       uint64_t *sram_bytes) {
  const uint8_t *view = iree_hal_cim_record_at(executable->view_defs, ordinal,
                                               CIMX_BUFFER_VIEW_DEF_SIZE);
  const uint32_t kind = iree_hal_cim_read_u32(view, 0);
  if (kind == CIMX_STORAGE_BINDING) {
    *binding_count =
        iree_max(*binding_count, iree_hal_cim_read_u32(view, 1) + 1);
  } else if (kind == CIMX_STORAGE_SRAM) {
    const uint32_t rows = iree_hal_cim_read_u32(view, 8);
    const uint32_t columns = iree_hal_cim_read_u32(view, 9);
    if (!rows || !columns)
      return iree_ok_status();
    uint64_t end = iree_hal_cim_read_u32(view, 4) +
                   (uint64_t)(rows - 1) * iree_hal_cim_read_u32(view, 10);
    if (end > CIMX_COMPETITION_SRAM_CAPACITY_BYTES)
      return iree_make_status(IREE_STATUS_OUT_OF_RANGE,
                              "CIM SRAM view exceeds capacity");
    end += (uint64_t)(columns - 1) * iree_hal_cim_read_u32(view, 11) +
           iree_hal_cim_read_u32(view, 2);
    if (end > CIMX_COMPETITION_SRAM_CAPACITY_BYTES)
      return iree_make_status(IREE_STATUS_OUT_OF_RANGE,
                              "CIM SRAM view exceeds capacity");
    // A workgroup-dependent address has no static bound without its grid.
    if (iree_hal_cim_read_u32(view, 5) || iree_hal_cim_read_u32(view, 6) ||
        iree_hal_cim_read_u32(view, 7))
      end = CIMX_COMPETITION_SRAM_CAPACITY_BYTES;
    *sram_bytes = iree_max(*sram_bytes, end);
  }
  return iree_ok_status();
}

static iree_status_t iree_hal_cim_export_dispatch_attrs(
    const iree_hal_cim_executable_t *executable, uint32_t export_ordinal,
    iree_hal_executable_dispatch_attrs_v0_t *attrs) {
  const uint8_t *export_def = iree_hal_cim_record_at(
      executable->export_defs, export_ordinal, CIMX_EXPORT_DEF_SIZE);
  const uint32_t program_start = iree_hal_cim_read_u32(export_def, 2);
  const uint32_t program_count = iree_hal_cim_read_u32(export_def, 3);
  uint32_t binding_count = 0;
  uint64_t sram_bytes = 0;

  for (uint32_t i = 0; i < program_count; ++i) {
    const uint8_t *program_op = iree_hal_cim_record_at(
        executable->program_ops, (iree_host_size_t)program_start + i,
        CIMX_PROGRAM_OP_DEF_SIZE);
    const uint32_t kind = iree_hal_cim_read_u32(program_op, 0);
    const uint32_t mode = iree_hal_cim_read_u32(program_op, 5);
    IREE_RETURN_IF_ERROR(
        iree_hal_cim_note_view(executable, iree_hal_cim_read_u32(program_op, 1),
                               &binding_count, &sram_bytes));
    if (kind != CIMX_OP_ELT || mode == CIMX_ELT_MODE_VV) {
      IREE_RETURN_IF_ERROR(iree_hal_cim_note_view(
          executable, iree_hal_cim_read_u32(program_op, 2), &binding_count,
          &sram_bytes));
    }
    if (kind == CIMX_OP_ELT || kind == CIMX_OP_BIT) {
      IREE_RETURN_IF_ERROR(iree_hal_cim_note_view(
          executable, iree_hal_cim_read_u32(program_op, 3), &binding_count,
          &sram_bytes));
    }
  }
  attrs->binding_count = (uint8_t)binding_count;
  attrs->local_memory_pages =
      (uint16_t)((sram_bytes +
                  IREE_HAL_EXECUTABLE_WORKGROUP_LOCAL_MEMORY_PAGE_SIZE - 1) /
                 IREE_HAL_EXECUTABLE_WORKGROUP_LOCAL_MEMORY_PAGE_SIZE);
  return iree_ok_status();
}

static iree_status_t
iree_hal_cim_executable_create(iree_const_byte_span_t executable_data,
                               iree_allocator_t host_allocator,
                               iree_hal_executable_t **out_executable) {
  *out_executable = NULL;
  const uint8_t *data = executable_data.data;
  if (executable_data.data_length < CIMX_HEADER_SIZE) {
    return iree_make_status(IREE_STATUS_INVALID_ARGUMENT,
                            "CIMX header is truncated");
  }
  if (iree_hal_cim_read_u32(data, 0) != CIMX_MAGIC ||
      iree_hal_cim_read_u32(data, 1) != CIMX_VERSION ||
      iree_hal_cim_read_u32(data, 2) != CIMX_COMPETITION_SRAM_CAPACITY_BYTES ||
      iree_hal_cim_read_u32(data, 3) != CIMX_COMPETITION_ARRAY_ROWS ||
      iree_hal_cim_read_u32(data, 4) != CIMX_COMPETITION_ARRAY_COLUMNS_BITS ||
      iree_hal_cim_payload_size(data) != executable_data.data_length) {
    return iree_make_status(IREE_STATUS_INVALID_ARGUMENT, "invalid CIMX v2");
  }

  const uint32_t export_count = iree_hal_cim_read_u32(data, 5);
  const uint32_t view_count = iree_hal_cim_read_u32(data, 6);
  const uint32_t program_op_count = iree_hal_cim_read_u32(data, 7);
  const uint32_t string_table_length = iree_hal_cim_read_u32(data, 8);
  const iree_host_size_t array_size =
      (iree_host_size_t)iree_hal_cim_read_u32(data, 3) *
      iree_hal_cim_read_u32(data, 4) / 8;

  iree_host_size_t total_size = 0;
  iree_host_size_t dispatch_attrs_offset = 0;
  iree_host_size_t export_names_offset = 0;
  iree_host_size_t name_storage_offset = 0;
  iree_host_size_t payload_offset = 0;
  iree_host_size_t array_offset = 0;
  IREE_RETURN_IF_ERROR(IREE_STRUCT_LAYOUT(
      sizeof(iree_hal_cim_executable_t), &total_size,
      IREE_STRUCT_FIELD_ALIGNED(export_count,
                                iree_hal_executable_dispatch_attrs_v0_t, 8,
                                &dispatch_attrs_offset),
      IREE_STRUCT_FIELD_ALIGNED(export_count, const char *,
                                iree_alignof(const char *),
                                &export_names_offset),
      IREE_STRUCT_FIELD_ALIGNED(string_table_length + export_count, char, 1,
                                &name_storage_offset),
      IREE_STRUCT_FIELD_ALIGNED(executable_data.data_length, uint8_t, 1,
                                &payload_offset),
      IREE_STRUCT_FIELD_ALIGNED(array_size, uint8_t, 64, &array_offset)));

  iree_hal_cim_executable_t *executable = NULL;
  IREE_RETURN_IF_ERROR(
      iree_allocator_malloc(host_allocator, total_size, (void **)&executable));
  iree_hal_local_executable_initialize(&iree_hal_cim_executable_vtable,
                                       host_allocator, &executable->base);

  uint8_t *payload = (uint8_t *)executable + payload_offset;
  memcpy(payload, executable_data.data, executable_data.data_length);
  executable->export_defs = payload + CIMX_HEADER_SIZE;
  executable->view_defs = iree_hal_cim_record_at(
      executable->export_defs, export_count, CIMX_EXPORT_DEF_SIZE);
  executable->program_ops = iree_hal_cim_record_at(
      executable->view_defs, view_count, CIMX_BUFFER_VIEW_DEF_SIZE);
  executable->string_table = iree_hal_cim_record_at(
      executable->program_ops, program_op_count, CIMX_PROGRAM_OP_DEF_SIZE);
  executable->data = executable->string_table + string_table_length;
  executable->array = (uint8_t *)executable + array_offset;

  iree_hal_executable_dispatch_attrs_v0_t *dispatch_attrs =
      (iree_hal_executable_dispatch_attrs_v0_t *)((uint8_t *)executable +
                                                  dispatch_attrs_offset);
  const char **export_names =
      (const char **)((uint8_t *)executable + export_names_offset);
  char *name_storage = (char *)executable + name_storage_offset;
  for (uint32_t i = 0; i < export_count; ++i) {
    const uint8_t *export_def = iree_hal_cim_record_at(executable->export_defs,
                                                       i, CIMX_EXPORT_DEF_SIZE);
    const uint32_t name_offset = iree_hal_cim_read_u32(export_def, 0);
    const uint32_t name_length = iree_hal_cim_read_u32(export_def, 1);
    export_names[i] = name_storage;
    memcpy(name_storage, executable->string_table + name_offset, name_length);
    name_storage[name_length] = 0;
    name_storage += name_length + 1;

    iree_status_t status =
        iree_hal_cim_export_dispatch_attrs(executable, i, &dispatch_attrs[i]);
    if (!iree_status_is_ok(status)) {
      iree_hal_executable_release((iree_hal_executable_t *)executable);
      return status;
    }
    dispatch_attrs[i].workgroup_size_x = 1;
    dispatch_attrs[i].workgroup_size_y = 1;
    dispatch_attrs[i].workgroup_size_z = 1;
  }

  executable->base.dispatch_attrs = dispatch_attrs;
  executable->base.export_count = export_count;
  executable->base.export_names = export_names;
  *out_executable = (iree_hal_executable_t *)executable;
  return iree_ok_status();
}

static void
iree_hal_cim_executable_destroy(iree_hal_executable_t *base_executable) {
  iree_hal_cim_executable_t *executable =
      (iree_hal_cim_executable_t *)base_executable;
  iree_allocator_t host_allocator = executable->base.host_allocator;
  iree_hal_local_executable_deinitialize(&executable->base);
  iree_allocator_free(host_allocator, executable);
}

static iree_host_size_t
iree_hal_cim_executable_function_count(iree_hal_executable_t *base_executable) {
  return ((iree_hal_cim_executable_t *)base_executable)->base.export_count;
}

static iree_status_t iree_hal_cim_executable_function_info(
    iree_hal_executable_t *base_executable,
    iree_hal_executable_function_t function,
    iree_hal_executable_function_info_t *out_info) {
  iree_hal_cim_executable_t *executable =
      (iree_hal_cim_executable_t *)base_executable;
  const uint32_t ordinal = iree_hal_executable_function_index(function);
  const iree_hal_executable_dispatch_attrs_v0_t *attrs =
      &executable->base.dispatch_attrs[ordinal];
  memset(out_info, 0, sizeof(*out_info));
  out_info->name =
      iree_make_cstring_view(executable->base.export_names[ordinal]);
  out_info->constant_count = attrs->constant_count;
  out_info->binding_count = attrs->binding_count;
  out_info->parameter_count = attrs->parameter_count;
  out_info->workgroup_size[0] = attrs->workgroup_size_x;
  out_info->workgroup_size[1] = attrs->workgroup_size_y;
  out_info->workgroup_size[2] = attrs->workgroup_size_z;
  return iree_ok_status();
}

static iree_status_t iree_hal_cim_executable_function_parameters(
    iree_hal_executable_t *base_executable,
    iree_hal_executable_function_t function, iree_host_size_t capacity,
    iree_hal_executable_function_parameter_t *out_parameters) {
  return iree_make_status(IREE_STATUS_UNIMPLEMENTED,
                          "CIM parameter reflection is not implemented");
}

static iree_status_t iree_hal_cim_executable_lookup_function_by_name(
    iree_hal_executable_t *base_executable, iree_string_view_t name,
    iree_hal_executable_function_t *out_function) {
  iree_hal_cim_executable_t *executable =
      (iree_hal_cim_executable_t *)base_executable;
  for (iree_host_size_t i = 0; i < executable->base.export_count; ++i) {
    if (iree_string_view_equal(
            name, iree_make_cstring_view(executable->base.export_names[i]))) {
      *out_function = iree_hal_executable_function_from_index(i);
      return iree_ok_status();
    }
  }
  *out_function = iree_hal_executable_function_invalid();
  return iree_make_status(IREE_STATUS_NOT_FOUND, "CIM export '%.*s' not found",
                          (int)name.size, name.data);
}

static iree_status_t iree_hal_cim_executable_lookup_global_by_name(
    iree_hal_executable_t *base_executable, iree_string_view_t name,
    iree_hal_queue_affinity_t queue_affinity, iree_hal_buffer_t **out_buffer) {
  *out_buffer = NULL;
  return iree_make_status(IREE_STATUS_UNIMPLEMENTED,
                          "CIM executable globals are not implemented");
}

static iree_hal_cim_view_t iree_hal_cim_resolve_view(
    iree_hal_cim_executable_t *executable, uint32_t ordinal,
    const iree_hal_executable_dispatch_state_v0_t *dispatch_state,
    const iree_hal_executable_workgroup_state_v0_t *workgroup_state) {
  const uint8_t *def = iree_hal_cim_record_at(executable->view_defs, ordinal,
                                              CIMX_BUFFER_VIEW_DEF_SIZE);
  const uint32_t storage_kind = iree_hal_cim_read_u32(def, 0);
  const uint32_t storage_ordinal = iree_hal_cim_read_u32(def, 1);
  const iree_host_size_t offset =
      iree_hal_cim_read_u32(def, 4) +
      (iree_host_size_t)iree_hal_cim_read_u32(def, 5) *
          workgroup_state->workgroup_id_x +
      (iree_host_size_t)iree_hal_cim_read_u32(def, 6) *
          workgroup_state->workgroup_id_y +
      (iree_host_size_t)iree_hal_cim_read_u32(def, 7) *
          workgroup_state->workgroup_id_z;
  uint8_t *root = NULL;
  switch (storage_kind) {
  case CIMX_STORAGE_SRAM:
    root = (uint8_t *)workgroup_state->local_memory;
    break;
  case CIMX_STORAGE_BINDING:
    root = (uint8_t *)dispatch_state->binding_ptrs[storage_ordinal];
    break;
  case CIMX_STORAGE_EMBEDDED_DATA:
    root = (uint8_t *)executable->data;
    break;
  case CIMX_STORAGE_ARRAY:
    root = executable->array;
    break;
  }
  return (iree_hal_cim_view_t){
      .data = root ? root + offset : NULL,
      .dtype = iree_hal_cim_read_u32(def, 2),
      .rank = iree_hal_cim_read_u32(def, 3),
      .extent = {iree_hal_cim_read_u32(def, 8), iree_hal_cim_read_u32(def, 9)},
      .stride = {iree_hal_cim_read_u32(def, 10),
                 iree_hal_cim_read_u32(def, 11)},
  };
}

static uint8_t *iree_hal_cim_view_element(iree_hal_cim_view_t view, uint32_t i,
                                          uint32_t j) {
  return view.data + (iree_host_size_t)i * view.stride[0] +
         (iree_host_size_t)j * view.stride[1];
}

static int64_t iree_hal_cim_load_integer(const uint8_t *data, uint32_t dtype) {
  uint32_t value = 0;
  memcpy(&value, data, dtype);
  if (dtype == 1)
    return (int8_t)value;
  if (dtype == 2)
    return (int16_t)value;
  return (int32_t)value;
}

static void iree_hal_cim_store_integer(uint8_t *data, uint32_t dtype,
                                       uint64_t value) {
  memcpy(data, &value, dtype);
}

static void iree_hal_cim_transfer(iree_hal_cim_view_t source,
                                  iree_hal_cim_view_t target) {
  for (uint32_t i = 0; i < target.extent[0]; ++i) {
    for (uint32_t j = 0; j < target.extent[1]; ++j) {
      memcpy(iree_hal_cim_view_element(target, i, j),
             iree_hal_cim_view_element(source, i, j), target.dtype);
    }
  }
}

// One bit-serial Array round: the selected activation bit is unsigned, so a
// signed activation is reconstructed by the caller subtracting the top round.
static void iree_hal_cim_bit(iree_hal_cim_view_t activation,
                             iree_hal_cim_view_t weight,
                             iree_hal_cim_view_t target, uint32_t index) {
  const uint32_t k_count = weight.extent[0];
  const uint32_t n_count = weight.extent[1];
  for (uint32_t n = 0; n < n_count; ++n) {
    uint8_t *output = target.rank == 1
                          ? iree_hal_cim_view_element(target, n, 0)
                          : iree_hal_cim_view_element(target, 0, n);
    iree_unaligned_store_le_u32((uint32_t *)output, 0);
  }
  // Array columns are contiguous; test each activation bit once per row.
  // Lowering and SRAM lifetimes keep activation and destination disjoint.
  for (uint32_t k = 0; k < k_count; ++k) {
    const uint8_t *input = activation.rank == 1
                               ? iree_hal_cim_view_element(activation, k, 0)
                               : iree_hal_cim_view_element(activation, 0, k);
    uint32_t raw = 0;
    memcpy(&raw, input, activation.dtype);
    if (!((raw >> index) & 1u))
      continue;
    for (uint32_t n = 0; n < n_count; ++n) {
      uint8_t *output = target.rank == 1
                            ? iree_hal_cim_view_element(target, n, 0)
                            : iree_hal_cim_view_element(target, 0, n);
      uint32_t sum = iree_unaligned_load_le_u32((const uint32_t *)output);
      sum += (int8_t)*iree_hal_cim_view_element(weight, k, n);
      iree_unaligned_store_le_u32((uint32_t *)output, sum);
    }
  }
}

static void iree_hal_cim_elt(iree_hal_cim_view_t lhs, iree_hal_cim_view_t rhs,
                             iree_hal_cim_view_t target, uint32_t op,
                             uint32_t mode, int64_t immediate) {
  const uint32_t count = target.extent[0] * target.extent[1];
  for (uint32_t index = 0; index < count; ++index) {
    const uint32_t i = target.rank == 1 ? index : index / target.extent[1];
    const uint32_t j = target.rank == 1 ? 0 : index % target.extent[1];
    const int64_t a = iree_hal_cim_load_integer(
        iree_hal_cim_view_element(lhs, i, j), lhs.dtype);
    const int64_t b =
        mode == CIMX_ELT_MODE_VI
            ? immediate
            : iree_hal_cim_load_integer(iree_hal_cim_view_element(rhs, i, j),
                                        rhs.dtype);
    uint64_t result = 0;
    switch (op) {
    case CIMX_ELT_OP_ADD:
      result = (uint64_t)a + (uint64_t)b;
      break;
    case CIMX_ELT_OP_SUB:
      result = (uint64_t)a - (uint64_t)b;
      break;
    case CIMX_ELT_OP_MUL:
      result = (uint64_t)a * (uint64_t)b;
      break;
    case CIMX_ELT_OP_DIV:
      result = (uint64_t)(a / b);
      break;
    }
    iree_hal_cim_store_integer(iree_hal_cim_view_element(target, i, j),
                               target.dtype, result);
  }
}

static iree_status_t iree_hal_cim_executable_issue_call(
    iree_hal_local_executable_t *base_executable, iree_host_size_t ordinal,
    const iree_hal_executable_dispatch_state_v0_t *dispatch_state,
    const iree_hal_executable_workgroup_state_v0_t *workgroup_state,
    uint32_t worker_id) {
  iree_hal_cim_executable_t *executable =
      (iree_hal_cim_executable_t *)base_executable;
  const iree_host_size_t sram_bytes =
      (iree_host_size_t)base_executable->dispatch_attrs[ordinal]
          .local_memory_pages *
      IREE_HAL_EXECUTABLE_WORKGROUP_LOCAL_MEMORY_PAGE_SIZE;
  if (workgroup_state->local_memory_size < sram_bytes) {
    return iree_make_status(IREE_STATUS_RESOURCE_EXHAUSTED,
                            "CIM workgroup SRAM is too small");
  }
  if (sram_bytes)
    memset(workgroup_state->local_memory, 0, sram_bytes);

  const uint8_t *export_def = iree_hal_cim_record_at(
      executable->export_defs, ordinal, CIMX_EXPORT_DEF_SIZE);
  const uint32_t program_start = iree_hal_cim_read_u32(export_def, 2);
  const uint32_t program_count = iree_hal_cim_read_u32(export_def, 3);
  for (uint32_t i = 0; i < program_count; ++i) {
    const uint8_t *program_op = iree_hal_cim_record_at(
        executable->program_ops, (iree_host_size_t)program_start + i,
        CIMX_PROGRAM_OP_DEF_SIZE);
    const uint32_t kind = iree_hal_cim_read_u32(program_op, 0);
    const uint32_t view0 = iree_hal_cim_read_u32(program_op, 1);
    const uint32_t view1 = iree_hal_cim_read_u32(program_op, 2);
    const uint32_t view2 = iree_hal_cim_read_u32(program_op, 3);
    const uint32_t mode = iree_hal_cim_read_u32(program_op, 5);
    iree_hal_cim_view_t a = iree_hal_cim_resolve_view(
        executable, view0, dispatch_state, workgroup_state);
    iree_hal_cim_view_t b = a;
    if (kind != CIMX_OP_ELT || mode == CIMX_ELT_MODE_VV) {
      b = iree_hal_cim_resolve_view(executable, view1, dispatch_state,
                                    workgroup_state);
    }
    switch (kind) {
    case CIMX_OP_TRANSFER:
    case CIMX_OP_ARRAY_LOAD:
      iree_hal_cim_transfer(a, b);
      break;
    case CIMX_OP_BIT: {
      iree_hal_cim_view_t c = iree_hal_cim_resolve_view(
          executable, view2, dispatch_state, workgroup_state);
      iree_hal_cim_bit(a, b, c,
                       (uint32_t)iree_hal_cim_read_i64(program_op, 24));
      break;
    }
    case CIMX_OP_ELT: {
      iree_hal_cim_view_t c = iree_hal_cim_resolve_view(
          executable, view2, dispatch_state, workgroup_state);
      iree_hal_cim_elt(a, b, c, iree_hal_cim_read_u32(program_op, 4), mode,
                       iree_hal_cim_read_i64(program_op, 24));
      break;
    }
    default:
      return iree_make_status(IREE_STATUS_INVALID_ARGUMENT,
                              "unknown CIM program op %u", kind);
    }
  }
  return iree_ok_status();
}

static const iree_hal_local_executable_vtable_t iree_hal_cim_executable_vtable =
    {
        .base =
            {
                .destroy = iree_hal_cim_executable_destroy,
                .function_count = iree_hal_cim_executable_function_count,
                .function_info = iree_hal_cim_executable_function_info,
                .function_parameters =
                    iree_hal_cim_executable_function_parameters,
                .lookup_function_by_name =
                    iree_hal_cim_executable_lookup_function_by_name,
                .lookup_global_by_name =
                    iree_hal_cim_executable_lookup_global_by_name,
            },
        .issue_call = iree_hal_cim_executable_issue_call,
};

static void iree_hal_cim_executable_loader_destroy(
    iree_hal_executable_loader_t *base_executable_loader) {
  iree_hal_cim_executable_loader_t *executable_loader =
      (iree_hal_cim_executable_loader_t *)base_executable_loader;
  iree_allocator_free(executable_loader->host_allocator, executable_loader);
}

static iree_status_t iree_hal_cim_executable_loader_infer_format(
    iree_hal_executable_loader_t *base_executable_loader,
    iree_hal_executable_caching_mode_t caching_mode,
    iree_const_byte_span_t executable_data,
    iree_host_size_t executable_format_capacity, char *executable_format,
    iree_host_size_t *out_inferred_size) {
  if (executable_data.data_length != 0 &&
      executable_data.data_length < CIMX_HEADER_SIZE) {
    return iree_make_status(IREE_STATUS_INCOMPATIBLE,
                            "executable is shorter than a CIMX header");
  }
  if (iree_hal_cim_read_u32(executable_data.data, 0) != CIMX_MAGIC) {
    return iree_make_status(IREE_STATUS_INCOMPATIBLE, "executable is not CIMX");
  }
  const iree_string_view_t format = IREE_SV(CIMX_EXECUTABLE_FORMAT);
  if (format.size >= executable_format_capacity) {
    return iree_make_status(IREE_STATUS_OUT_OF_RANGE,
                            "executable format buffer too small");
  }
  memcpy(executable_format, format.data, format.size);
  executable_format[format.size] = 0;
  *out_inferred_size = executable_data.data_length
                           ? executable_data.data_length
                           : iree_hal_cim_payload_size(executable_data.data);
  return iree_ok_status();
}

static bool iree_hal_cim_executable_loader_query_support(
    iree_hal_executable_loader_t *base_executable_loader,
    iree_hal_executable_caching_mode_t caching_mode,
    iree_string_view_t executable_format) {
  return iree_string_view_equal(executable_format,
                                IREE_SV(CIMX_EXECUTABLE_FORMAT));
}

static iree_status_t iree_hal_cim_executable_loader_try_load(
    iree_hal_executable_loader_t *base_executable_loader,
    const iree_hal_executable_params_t *executable_params,
    iree_host_size_t worker_capacity, iree_hal_executable_t **out_executable) {
  iree_hal_cim_executable_loader_t *executable_loader =
      (iree_hal_cim_executable_loader_t *)base_executable_loader;
  return iree_hal_cim_executable_create(executable_params->executable_data,
                                        executable_loader->host_allocator,
                                        out_executable);
}

static const iree_hal_executable_loader_vtable_t
    iree_hal_cim_executable_loader_vtable = {
        .destroy = iree_hal_cim_executable_loader_destroy,
        .infer_format = iree_hal_cim_executable_loader_infer_format,
        .query_support = iree_hal_cim_executable_loader_query_support,
        .try_load = iree_hal_cim_executable_loader_try_load,
};

iree_status_t iree_hal_cim_executable_loader_create(
    iree_allocator_t host_allocator,
    iree_hal_executable_loader_t **out_executable_loader) {
  *out_executable_loader = NULL;
  iree_hal_cim_executable_loader_t *executable_loader = NULL;
  IREE_RETURN_IF_ERROR(iree_allocator_malloc(
      host_allocator, sizeof(*executable_loader), (void **)&executable_loader));
  iree_hal_executable_loader_initialize(
      &iree_hal_cim_executable_loader_vtable,
      iree_hal_executable_import_provider_null(), &executable_loader->base);
  executable_loader->host_allocator = host_allocator;
  *out_executable_loader = &executable_loader->base;
  return iree_ok_status();
}
