module {
  func.func @unsigned_named(%src: memref<1x2xi8>, %weight: memref<2x1xi8>, %dst: memref<1x1xi32>) {
    linalg.matmul {cast = #linalg.type_fn<cast_unsigned>}
      ins(%src, %weight : memref<1x2xi8>, memref<2x1xi8>)
      outs(%dst : memref<1x1xi32>)
    return
  }
}
