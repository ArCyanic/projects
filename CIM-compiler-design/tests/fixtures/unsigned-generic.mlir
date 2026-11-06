module {
  func.func @unsigned_generic(%src: memref<1x2xi8>, %weight: memref<2x1xi8>, %dst: memref<1x1xi32>) {
    linalg.generic {
      indexing_maps = [affine_map<(m,n,k)->(m,k)>, affine_map<(m,n,k)->(k,n)>, affine_map<(m,n,k)->(m,n)>],
      iterator_types = ["parallel", "parallel", "reduction"]
    } ins(%src, %weight : memref<1x2xi8>, memref<2x1xi8>) outs(%dst : memref<1x1xi32>) {
    ^bb0(%a: i8, %b: i8, %acc: i32):
      %a32 = arith.extui %a : i8 to i32
      %b32 = arith.extsi %b : i8 to i32
      %mul = arith.muli %a32, %b32 : i32
      %sum = arith.addi %acc, %mul : i32
      linalg.yield %sum : i32
    }
    return
  }
}
