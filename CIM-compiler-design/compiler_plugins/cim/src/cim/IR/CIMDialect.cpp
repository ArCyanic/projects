#include "cim/IR/CIMDialect.h"

#include "cim/IR/CIMOps.h"
#include "mlir/IR/DialectImplementation.h"
#include "llvm/ADT/TypeSwitch.h"

#include "cim/IR/CIMEnums.cpp.inc"
#define GET_ATTRDEF_CLASSES
#include "cim/IR/CIMAttrs.cpp.inc"

namespace mlir::iree_compiler::IREE::CIM {

void CIMDialect::initialize() {
  addAttributes<
#define GET_ATTRDEF_LIST
#include "cim/IR/CIMAttrs.cpp.inc"
      >();
  addOperations<
#define GET_OP_LIST
#include "cim/IR/CIMOps.cpp.inc"
      >();
}

} // namespace mlir::iree_compiler::IREE::CIM

#include "cim/IR/CIMDialect.cpp.inc"
