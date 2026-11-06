#include "cim_executable.h"

#include "iree/base/api.h"
#include "iree/hal/allocator.h"
#include "iree/hal/driver_registry.h"
#include "iree/hal/drivers/local_sync/sync_driver.h"

static iree_status_t iree_hal_cim_driver_factory_enumerate(
    void *self, iree_host_size_t *out_driver_info_count,
    const iree_hal_driver_info_t **out_driver_infos) {
  static const iree_hal_driver_info_t driver_info = {
      .driver_name = IREE_SVL("cim"),
      .full_name = IREE_SVL("CIM execution using IREE local-sync"),
  };
  *out_driver_info_count = 1;
  *out_driver_infos = &driver_info;
  return iree_ok_status();
}

static iree_status_t iree_hal_cim_driver_factory_try_create(
    void *self, iree_string_view_t driver_name, iree_allocator_t host_allocator,
    iree_hal_driver_t **out_driver) {
  if (!iree_string_view_equal(driver_name, IREE_SV("cim"))) {
    return iree_make_status(IREE_STATUS_UNAVAILABLE,
                            "CIM factory does not provide driver '%.*s'",
                            (int)driver_name.size, driver_name.data);
  }

  iree_hal_executable_loader_t *loader = NULL;
  iree_status_t status =
      iree_hal_cim_executable_loader_create(host_allocator, &loader);

  iree_hal_allocator_t *device_allocator = NULL;
  if (iree_status_is_ok(status)) {
    status = iree_hal_allocator_create_heap(IREE_SV("local"), host_allocator,
                                            host_allocator, &device_allocator);
  }

  if (iree_status_is_ok(status)) {
    iree_hal_sync_device_params_t params;
    iree_hal_sync_device_params_initialize(&params);
    status = iree_hal_sync_driver_create(IREE_SV("local"), &params, 1, &loader,
                                         device_allocator, host_allocator,
                                         out_driver);
  }

  iree_hal_allocator_release(device_allocator);
  iree_hal_executable_loader_release(loader);
  return status;
}

IREE_API_EXPORT iree_status_t
iree_hal_cim_driver_module_register(iree_hal_driver_registry_t *registry) {
  static const iree_hal_driver_factory_t factory = {
      .self = NULL,
      .enumerate = iree_hal_cim_driver_factory_enumerate,
      .try_create = iree_hal_cim_driver_factory_try_create,
  };
  return iree_hal_driver_registry_register_factory(registry, &factory);
}
