module {
  func.func @transposed_activation(%src: memref<2x1xi8>, %weight: memref<2x1xi8>, %dst: memref<1x1xi32>) {
    linalg.matmul indexing_maps = [affine_map<(m,n,k)->(k,m)>, affine_map<(m,n,k)->(k,n)>, affine_map<(m,n,k)->(m,n)>]
      ins(%src, %weight : memref<2x1xi8>, memref<2x1xi8>)
      outs(%dst : memref<1x1xi32>)
    return
  }
}
