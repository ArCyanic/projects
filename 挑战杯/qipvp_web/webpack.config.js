import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'


module.exports = {
    // ...
    plugins: [
        Components({
            resolvers: [ElementPlusResolver()],
        }),
    ],
}
