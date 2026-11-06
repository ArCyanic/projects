#layout = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer, ReadOnly>, #hal.pipeline.binding<storage_buffer>], flags = None>
module {
  hal.executable public @probe {
    hal.executable.variant public @cim_executable target(<"cim", "cim-executable", {profile = "competition"}>) {
      hal.executable.export public @probe ordinal(0) layout(#layout)
      builtin.module {
        memref.global "private" constant @weight : memref<6xi8> = dense<[99, 98, 1, 2, 3, 4]>
        func.func @probe() {
          %c0 = arith.constant 0 : index
          %c2 = arith.constant 2 : index
          %raw = memref.get_global @weight : memref<6xi8>
          %v = memref.view %raw[%c2][] : memref<6xi8> to memref<2x2xi8>
          %w = memref.cast %v : memref<2x2xi8> to memref<2x2xi8, strided<[2, 1], offset: ?>>
          %src = hal.interface.binding.subspan layout(#layout) binding(0) offset(%c0) : memref<1x2xi8>
          %dst = hal.interface.binding.subspan layout(#layout) binding(1) offset(%c0) : memref<1x4xi32>
          %d0 = memref.subview %dst[0,0][1,2][1,1] : memref<1x4xi32> to memref<1x2xi32, strided<[4,1]>>
          %d1 = memref.subview %dst[0,2][1,2][1,1] : memref<1x4xi32> to memref<1x2xi32, strided<[4,1], offset: 2>>
          cim.mvm ins(%src, %w : memref<1x2xi8>, memref<2x2xi8, strided<[2, 1], offset: ?>>) outs(%d0 : memref<1x2xi32, strided<[4,1]>>)
          cim.mvm ins(%src, %w : memref<1x2xi8>, memref<2x2xi8, strided<[2, 1], offset: ?>>) outs(%d1 : memref<1x2xi32, strided<[4,1], offset: 2>>)
          return
        }
      }
    }
  }
}
