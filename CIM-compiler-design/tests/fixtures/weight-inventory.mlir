module {
  func.func @resource_inventory(%a: tensor<1x256xi8>, %b: tensor<1x256xi8>, %c: tensor<1x768xi8>) -> (tensor<1x128xi32>, tensor<1x128xi32>, tensor<1x512xi32>) {
    %w0 = arith.constant dense<1> : tensor<256x128xi8>
    %w1 = arith.constant dense<2> : tensor<256x128xi8>
    %large = arith.constant dense<3> : tensor<768x512xi8>
    %zero = arith.constant 0 : i32
    %empty = tensor.empty() : tensor<1x128xi32>
    %init = linalg.fill ins(%zero : i32) outs(%empty : tensor<1x128xi32>) -> tensor<1x128xi32>
    %large_empty = tensor.empty() : tensor<1x512xi32>
    %large_init = linalg.fill ins(%zero : i32) outs(%large_empty : tensor<1x512xi32>) -> tensor<1x512xi32>
    %y0 = linalg.matmul ins(%a, %w0 : tensor<1x256xi8>, tensor<256x128xi8>) outs(%init : tensor<1x128xi32>) -> tensor<1x128xi32>
    %y1 = linalg.matmul ins(%b, %w1 : tensor<1x256xi8>, tensor<256x128xi8>) outs(%init : tensor<1x128xi32>) -> tensor<1x128xi32>
    %y2 = linalg.matmul ins(%c, %large : tensor<1x768xi8>, tensor<768x512xi8>) outs(%large_init : tensor<1x512xi32>) -> tensor<1x512xi32>
    return %y0, %y1, %y2 : tensor<1x128xi32>, tensor<1x128xi32>, tensor<1x512xi32>
  }
}
