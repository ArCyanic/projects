#ifndef CIM_RUNTIME_CIM_EXECUTABLE_H_
#define CIM_RUNTIME_CIM_EXECUTABLE_H_

#include "iree/hal/local/executable_loader.h"

#ifdef __cplusplus
extern "C" {
#endif

iree_status_t iree_hal_cim_executable_loader_create(
    iree_allocator_t host_allocator,
    iree_hal_executable_loader_t **out_executable_loader);

#ifdef __cplusplus
} // extern "C"
#endif

#endif // CIM_RUNTIME_CIM_EXECUTABLE_H_
