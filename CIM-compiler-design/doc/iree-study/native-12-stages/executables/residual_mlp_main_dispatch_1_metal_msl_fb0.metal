#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct _6
{
    float4 _m0[1];
};

struct spvDescriptorSetBuffer0
{
    device _6* _resource_var_0_0_ [[id(0)]];
    device _6* _resource_var_0_1_ [[id(1)]];
    device _6* _resource_var_0_2_ [[id(2)]];
    device _6* _resource_var_0_3_ [[id(3)]];
    device _6* _resource_var_0_4_ [[id(4)]];
};

kernel void main_dispatch_1_matmul_16x32x64_f32(constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]])
{
    float4 _37;
    _37 = float4(0.0);
    float4 _32;
    for (uint _36 = 0u; int(_36) < int(64u); )
    {
        uint _41 = _36 / 4u;
        uint _42 = (gl_LocalInvocationID.y * 16u) + _41;
        uint _46 = _36 * 8u;
        uint _47 = _46 + gl_LocalInvocationID.x;
        float4 _71 = fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_42].w), (*spvDescriptorSet0._resource_var_0_1_)._m0[_47 + 24u], fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_42].z), (*spvDescriptorSet0._resource_var_0_1_)._m0[_47 + 16u], fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_42].y), (*spvDescriptorSet0._resource_var_0_1_)._m0[_47 + 8u], fma(float4((*spvDescriptorSet0._resource_var_0_0_)._m0[_42].x), (*spvDescriptorSet0._resource_var_0_1_)._m0[_47], _37))));
        _32 = _71;
        _36 += 4u;
        _37 = _71;
        continue;
    }
    uint _77 = (gl_LocalInvocationID.y * 8u) + gl_LocalInvocationID.x;
    (*spvDescriptorSet0._resource_var_0_4_)._m0[_77] = (_32 + (*spvDescriptorSet0._resource_var_0_2_)._m0[gl_LocalInvocationID.x]) + (*spvDescriptorSet0._resource_var_0_3_)._m0[_77];
}

