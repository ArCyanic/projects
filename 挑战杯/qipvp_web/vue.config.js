module.exports = {
    devServer: {
        open: true, //是否自动弹出浏览器页面
        proxy: {
            '/api': {
                target: 'http://localhost:8000', //API服务器的地址
                ws: true,  //代理websockets
                changeOrigin: true, // 虚拟的站点需要更管origin
                pathRewrite: {   //重写路径 比如'/api/aaa/ccc'重写为'/aaa/ccc'
                    '^/api': ''
                }
            }
        },
    }
}
