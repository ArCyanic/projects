#ifndef CIM_COMPILER_PLUGINS_CIM_IR_CIMOPS_H_
#define CIM_COMPILER_PLUGINS_CIM_IR_CIMOPS_H_

#include "cim/IR/CIMDialect.h"
#include "mlir/Bytecode/BytecodeOpInterface.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Operation.h"
#include "mlir/Interfaces/SideEffectInterfaces.h"

#include "cim/IR/CIMEnums.h.inc" // IWYU pragma: keep

#define GET_ATTRDEF_CLASSES
#include "cim/IR/CIMAttrs.h.inc" // IWYU pragma: keep

#define GET_OP_CLASSES
#include "cim/IR/CIMOps.h.inc" // IWYU pragma: keep

#endif // CIM_COMPILER_PLUGINS_CIM_IR_CIMOPS_H_
