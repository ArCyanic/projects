module {
  func.func @transpose_a(%a: tensor<2x2xi8>, %b: tensor<2x2xi8>) -> (tensor<2x1xi32>, tensor<2x1xi32>) {
    %w0 = arith.constant dense<[[1], [2]]> : tensor<2x1xi8>
    %w1 = arith.constant dense<[[3], [4]]> : tensor<2x1xi8>
    %zero = arith.constant 0 : i32
    %empty = tensor.empty() : tensor<2x1xi32>
    %init = linalg.fill ins(%zero : i32) outs(%empty : tensor<2x1xi32>) -> tensor<2x1xi32>
    %y0 = linalg.matmul indexing_maps = [affine_map<(m,n,k) -> (k,m)>, affine_map<(m,n,k) -> (k,n)>, affine_map<(m,n,k) -> (m,n)>] ins(%a, %w0 : tensor<2x2xi8>, tensor<2x1xi8>) outs(%init : tensor<2x1xi32>) -> tensor<2x1xi32>
    %y1 = linalg.matmul indexing_maps = [affine_map<(m,n,k) -> (k,m)>, affine_map<(m,n,k) -> (k,n)>, affine_map<(m,n,k) -> (m,n)>] ins(%b, %w1 : tensor<2x2xi8>, tensor<2x1xi8>) outs(%init : tensor<2x1xi32>) -> tensor<2x1xi32>
    return %y0, %y1 : tensor<2x1xi32>, tensor<2x1xi32>
  }
}
