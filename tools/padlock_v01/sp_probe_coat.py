"""Read available native channels and shader API before adding the varnish."""
import json
import substance_painter.js as JS
import substance_painter.textureset as T
print('COAT_CHANNELS',[n for n in T.ChannelType.__members__ if 'Coat' in n or n in ('User0','User1')])
print('SHADER_API',JS.evaluate('JSON.stringify(Object.keys(alg.shaders))'))
print('SHADER_INSTANCES',JS.evaluate('JSON.stringify(alg.shaders.instances())'))
print('SHADER_OBJECT',JS.evaluate('JSON.stringify(alg.shaders.shaderInstancesToObject())'))
print('FUNCTION_SIGNATURE',JS.evaluate('alg.shaders.updateShaderInstance.toString()'))
