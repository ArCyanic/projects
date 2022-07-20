import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// import { ElButton, ElContainer, ElAside, ElMenu, ElSubMenu } from 'element-plus'
const app = createApp(App)
app.use(ElementPlus)
// app.use(ElButton)
// app.use(ElContainer)
// app.use(ElAside)
// app.use(ElMenu)
// app.use(ElSubMenu)
app.use(store).use(router).mount('#app')
