# Initial cache for the native IREE + CIM build. Explicit -D options can override
# these defaults; source files and compiler/runtime targets stay owned by IREE.
set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type")
set(IREE_CMAKE_PLUGIN_PATHS "${CMAKE_CURRENT_LIST_DIR}/../compiler_plugins/cim"
    CACHE STRING "Compiler and runtime plugin roots")
set(IREE_EXTERNAL_HAL_DRIVERS cim CACHE STRING "External HAL drivers")

set(IREE_BUILD_TESTS OFF CACHE BOOL "Build upstream tests")
set(IREE_BUILD_SAMPLES OFF CACHE BOOL "Build upstream samples")
set(IREE_BUILD_BINDINGS_TFLITE OFF CACHE BOOL "Build TFLite bindings")
set(IREE_BUILD_BINDINGS_TFLITE_JAVA OFF CACHE BOOL "Build TFLite Java bindings")
set(IREE_TARGET_BACKEND_DEFAULTS OFF CACHE BOOL "Enable default target backends")
set(IREE_HAL_DRIVER_DEFAULTS OFF CACHE BOOL "Enable default HAL drivers")
set(IREE_HAL_DRIVER_LOCAL_SYNC ON CACHE BOOL "Build the CIM runtime's host driver")
set(IREE_INPUT_STABLEHLO OFF CACHE BOOL "Build StableHLO input conversion")
set(IREE_INPUT_TOSA OFF CACHE BOOL "Build TOSA input conversion")
set(IREE_OUTPUT_FORMAT_C OFF CACHE BOOL "Build C output support")
