spirv.module Logical GLSL450 requires #spirv.vce<v1.0, [Shader, Matrix], [SPV_KHR_storage_buffer_storage_class]> {
  spirv.GlobalVariable @__builtin__LocalInvocationId__ built_in("LocalInvocationId") : !spirv.ptr<vector<3xi32>, Input>
  spirv.GlobalVariable @__resource_var_0_0_ bind(0, 0) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_1_ bind(0, 1) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_2_ bind(0, 2) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_3_ bind(0, 3) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.GlobalVariable @__resource_var_0_4_ bind(0, 4) : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
  spirv.func @main_dispatch_1_matmul_16x32x64_f32() "None" {
    %cst8_i32 = spirv.Constant 8 : i32
    %cst24_i32 = spirv.Constant 24 : i32
    %cst16_i32 = spirv.Constant 16 : i32
    %cst4_i32 = spirv.Constant 4 : i32
    %cst64_i32 = spirv.Constant 64 : i32
    %cst0_i32 = spirv.Constant 0 : i32
    %cst_vec_4xf32 = spirv.Constant dense<0.000000e+00> : vector<4xf32>
    %__resource_var_0_0__addr = spirv.mlir.addressof @__resource_var_0_0_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__resource_var_0_1__addr = spirv.mlir.addressof @__resource_var_0_1_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__resource_var_0_2__addr = spirv.mlir.addressof @__resource_var_0_2_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__resource_var_0_3__addr = spirv.mlir.addressof @__resource_var_0_3_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__resource_var_0_4__addr = spirv.mlir.addressof @__resource_var_0_4_ : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>
    %__builtin__LocalInvocationId___addr = spirv.mlir.addressof @__builtin__LocalInvocationId__ : !spirv.ptr<vector<3xi32>, Input>
    %0 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
    %1 = spirv.CompositeExtract %0[1 : i32] : vector<3xi32>
    %2 = spirv.Load "Input" %__builtin__LocalInvocationId___addr : vector<3xi32>
    %3 = spirv.CompositeExtract %2[0 : i32] : vector<3xi32>
    %4 = spirv.Variable : !spirv.ptr<vector<4xf32>, Function>
    spirv.mlir.loop {
      spirv.Branch ^bb1(%cst0_i32, %cst_vec_4xf32 : i32, vector<4xf32>)
    ^bb1(%15: i32, %16: vector<4xf32>):  // 2 preds: ^bb0, ^bb2
      %17 = spirv.SLessThan %15, %cst64_i32 : i32
      spirv.BranchConditional %17, ^bb2, ^bb3
    ^bb2:  // pred: ^bb1
      %18 = spirv.IMul %1, %cst16_i32 : i32
      %19 = spirv.UDiv %15, %cst4_i32 : i32
      %20 = spirv.IAdd %18, %19 : i32
      %21 = spirv.AccessChain %__resource_var_0_0__addr[%cst0_i32, %20] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %22 = spirv.Load "StorageBuffer" %21 : vector<4xf32>
      %23 = spirv.IMul %15, %cst8_i32 : i32
      %24 = spirv.IAdd %23, %3 : i32
      %25 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %24] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %26 = spirv.Load "StorageBuffer" %25 : vector<4xf32>
      %27 = spirv.IAdd %24, %cst8_i32 : i32
      %28 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %27] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %29 = spirv.Load "StorageBuffer" %28 : vector<4xf32>
      %30 = spirv.IAdd %24, %cst16_i32 : i32
      %31 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %30] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %32 = spirv.Load "StorageBuffer" %31 : vector<4xf32>
      %33 = spirv.IAdd %24, %cst24_i32 : i32
      %34 = spirv.AccessChain %__resource_var_0_1__addr[%cst0_i32, %33] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
      %35 = spirv.Load "StorageBuffer" %34 : vector<4xf32>
      %36 = spirv.CompositeExtract %22[0 : i32] : vector<4xf32>
      %37 = spirv.CompositeConstruct %36, %36, %36, %36 : (f32, f32, f32, f32) -> vector<4xf32>
      %38 = spirv.GL.Fma %37, %26, %16 : vector<4xf32>
      %39 = spirv.CompositeExtract %22[1 : i32] : vector<4xf32>
      %40 = spirv.CompositeConstruct %39, %39, %39, %39 : (f32, f32, f32, f32) -> vector<4xf32>
      %41 = spirv.GL.Fma %40, %29, %38 : vector<4xf32>
      %42 = spirv.CompositeExtract %22[2 : i32] : vector<4xf32>
      %43 = spirv.CompositeConstruct %42, %42, %42, %42 : (f32, f32, f32, f32) -> vector<4xf32>
      %44 = spirv.GL.Fma %43, %32, %41 : vector<4xf32>
      %45 = spirv.CompositeExtract %22[3 : i32] : vector<4xf32>
      %46 = spirv.CompositeConstruct %45, %45, %45, %45 : (f32, f32, f32, f32) -> vector<4xf32>
      %47 = spirv.GL.Fma %46, %35, %44 : vector<4xf32>
      spirv.Store "Function" %4, %47 : vector<4xf32>
      %48 = spirv.IAdd %15, %cst4_i32 : i32
      spirv.Branch ^bb1(%48, %47 : i32, vector<4xf32>)
    ^bb3:  // pred: ^bb1
      spirv.mlir.merge
    }
    %5 = spirv.Load "Function" %4 : vector<4xf32>
    %6 = spirv.AccessChain %__resource_var_0_2__addr[%cst0_i32, %3] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
    %7 = spirv.Load "StorageBuffer" %6 : vector<4xf32>
    %8 = spirv.IMul %1, %cst8_i32 : i32
    %9 = spirv.IAdd %8, %3 : i32
    %10 = spirv.AccessChain %__resource_var_0_3__addr[%cst0_i32, %9] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
    %11 = spirv.Load "StorageBuffer" %10 : vector<4xf32>
    %12 = spirv.FAdd %5, %7 : vector<4xf32>
    %13 = spirv.FAdd %12, %11 : vector<4xf32>
    %14 = spirv.AccessChain %__resource_var_0_4__addr[%cst0_i32, %9] : !spirv.ptr<!spirv.struct<(!spirv.rtarray<vector<4xf32>, stride=16> [0])>, StorageBuffer>, i32, i32 -> !spirv.ptr<vector<4xf32>, StorageBuffer>
    spirv.Store "StorageBuffer" %14, %13 : vector<4xf32>
    spirv.Return
  }
  spirv.EntryPoint "GLCompute" @main_dispatch_1_matmul_16x32x64_f32, @__builtin__LocalInvocationId__
  spirv.ExecutionMode @main_dispatch_1_matmul_16x32x64_f32 "LocalSize", 8, 16, 1
}