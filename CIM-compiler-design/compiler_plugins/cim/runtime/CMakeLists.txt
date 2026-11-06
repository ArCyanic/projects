iree_cc_library(
  PACKAGE cim_runtime
  NAME driver
  SRCS
    "cim_executable.c"
    "driver.c"
  INCLUDES
    "${CMAKE_CURRENT_LIST_DIR}/../src"
  DEPS
    iree::base
    iree::hal
    iree::hal::drivers::local_sync::sync_driver
    iree::hal::local
  PUBLIC
)
