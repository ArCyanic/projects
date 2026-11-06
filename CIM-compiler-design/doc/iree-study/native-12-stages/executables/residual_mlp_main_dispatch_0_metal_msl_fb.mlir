spirv.module Logical GLSL450 requires #spirv.vce<v1.0, [Shader, Matrix], [SPV_KHR_storage_buffer_storage_class]> {
  spirv.GlobalVariable @__builtin__LocalInvocationId__ built_in("LocalInvocationId") : !spirv.ptr<vector<3xi32>, Input>
  spirv.GlobalVariable @__resource_var_0_0_ bind(0, 0) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_1_ bind(0, 1) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_2_ bind(0, 2) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_3_ bind(0, 3) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.func @main_dispatch_0_matmul_16x64x32_f32() "None" {
    %cst16_i32 = spirv.Constant 16 : i32
    %cst48_i32 = spirv.Constant 48 : i32
    %cst8_i32 = spirv.Constant 8 : i32
    %cst4_i32 = spirv.Constant 4 : i32
    %cst32_i32 = spirv.Constant 32 : i32
    %cst0_i32 = spirv.Constant 0 : i32
    %cst_vec_4xf32 = spirv.Constant dense<0.000000e+00> : vector<4xf32>
    %__resource_var_0_0__addr = spirv.mlir.addressof @__resource_var_0_0_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__resource_var_0_1__addr = spirv.mlir.addressof @__resource_var_0_1_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__resource_var_0_2__addr = spirv.mlir.addressof @__resource_var_0_2_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__resource_var_0_3__addr = spirv.mlir.addressof @__resource_var_0_3_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__builtin__LocalInvocationId___addr = spirv.mlir.addressof @__builtin__LocalInvocationId__ : !spirv.ptr<vector<3xi32>, Input>
    %0 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
    %1 = spirv.CompositeExtract %0[1 : i32] : vector<3xi32>
    %2 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
    %3 = spirv.CompositeExtract %2[0 : i32] : vector<3xi32>
    %4 = spirv.Variable : !spirv.ptr<vector<4xf32>, Function>
    spirv.mlir.loop {
      spirv.Branch ^bb1(%cst0_i32, %cst_vec_4xf32 : i32, vector<4xf32>)
    ^bb1(%17: i32, %18: vector<4xf32>):  // 2 preds: ^bb0, ^bb2
      %19 = spirv.SLessThan %17, %cst32_i32 : i32
      spirv.BranchConditional %19, ^bb2, ^bb3
    ^bb2:  // pred: ^bb1
      %20 = spirv.IMul %1, %cst8_i32 : i32
      %21 = spirv.UDiv %17, %cst4_i32 : i32
      %22 = spirv.IAdd %20, %21 : i32
      %23 = spirv.AccessChain %__resource_var_0_0__addr[%cst0_i32, %22] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %24 = spirv.Load "StorageBuffer" %23 : vector<4xf32>
      %25 = spirv.IMul %17, %cst16_i32 : i32
      %26 = spirv.IAdd %25, %3 : i32
      %27 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %26] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %28 = spirv.Load "StorageBuffer" %27 : vector<4xf32>
      %29 = spirv.IAdd %26, %cst16_i32 : i32
      %30 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %29] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %31 = spirv.Load "StorageBuffer" %30 : vector<4xf32>
      %32 = spirv.IAdd %26, %cst32_i32 : i32
      %33 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %32] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %34 = spirv.Load "StorageBuffer" %33 : vector<4xf32>
      %35 = spirv.IAdd %26, %cst48_i32 : i32
      %36 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %35] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %37 = spirv.Load "StorageBuffer" %36 : vector<4xf32>
      %38 = spirv.CompositeExtract %24[0 : i32] : vector<4xf32>
      %39 = spirv.CompositeConstruct %38, %38, %38, %38 : (f32, f32, f32, f32) -> vector<4xf32>
      %40 = spirv.GL.Fma %39, %28, %18 : vector<4xf32>
      %41 = spirv.CompositeExtract %24[1 : i32] : vector<4xf32>
      %42 = spirv.CompositeConstruct %41, %41, %41, %41 : (f32, f32, f32, f32) -> vector<4xf32>
      %43 = spirv.GL.Fma %42, %31, %40 : vector<4xf32>
      %44 = spirv.CompositeExtract %24[2 : i32] : vector<4xf32>
      %45 = spirv.CompositeConstruct %44, %44, %44, %44 : (f32, f32, f32, f32) -> vector<4xf32>
      %46 = spirv.GL.Fma %45, %34, %43 : vector<4xf32>
      %47 = spirv.CompositeExtract %24[3 : i32] : vector<4xf32>
      %48 = spirv.CompositeConstruct %47, %47, %47, %47 : (f32, f32, f32, f32) -> vector<4xf32>
      %49 = spirv.GL.Fma %48, %37, %46 : vector<4xf32>
      spirv.Store "Function" %4, %49 : vector<4xf32>
      %50 = spirv.IAdd %17, %cst4_i32 : i32
      spirv.Branch ^bb1(%50, %49 : i32, vector<4xf32>)
    ^bb3:  // pred: ^bb1
      spirv.mlir.merge
    }
    %5 = spirv.Load "Function" %4 : vector<4xf32>
    %6 = spirv.AccessChain %__resource_var_0_2__addr[%cst0_i32, %3] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
    %7 = spirv.Load "StorageBuffer" %6 : vector<4xf32>
    %8 = spirv.FAdd %5, %7 : vector<4xf32>
    %9 = spirv.GL.FMax %8, %cst_vec_4xf32 : vector<4xf32>
    %10 = spirv.IsNan %8 : vector<4xf32>
    %11 = spirv.IsNan %cst_vec_4xf32 : vector<4xf32>
    %12 = spirv.Select %10, %8, %9 : vector<4xi1>, vector<4xf32>
    %13 = spirv.Select %11, %cst_vec_4xf32, %12 : vector<4xi1>, vector<4xf32>
    %14 = spirv.IMul %1, %cst16_i32 : i32
    %15 = spirv.IAdd %14, %3 : i32
    %16 = spirv.AccessChain %__resource_var_0_3__addr[%cst0_i32, %15] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
    spirv.Store "StorageBuffer" %16, %13 : vector<4xf32>
    spirv.Return
  }
  spirv.EntryPoint "GLCompute" @main_dispatch_0_matmul_16x64x32_f32, @__builtin__LocalInvocationId__
  spirv.ExecutionMode @main_dispatch_0_matmul_16x64x32_f32 "LocalSize", 16, 16, 1
}