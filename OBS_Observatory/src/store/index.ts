import { defineStore } from "pinia";

export const useStore = defineStore({
    id: 'user',

    state: () => {
        return {
            isCollapsed: false as Boolean 
        }
    },

    getters: {

    },

    actions: {
        toggleSidebar() {
            this.isCollapsed = !this.isCollapsed
        }
    }

})