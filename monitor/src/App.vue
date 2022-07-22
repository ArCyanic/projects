<script setup lang="ts">
import { onBeforeMount, ref } from 'vue';
import { fetchData } from './utils';

import { mockDays } from "./types";

import StackedColumn from './components/StackedColumn.vue';
import Table from './components/Table.vue'
import MixedLineBar from './components/MixedLineBar.vue';

const radio = ref('None') // Table | Stack
const chartIndicator = ref('None') // Series | Single
const index = ref(0)

let receiver: mockDays = { data: [] }
onBeforeMount(async () => {
  await fetchData('/api/mockDays', receiver)
  chartIndicator.value = 'Series'
  radio.value = 'Stack'
})

const check = (i: number) => {
  chartIndicator.value = 'Single'
  index.value = i
}

const back = () => {
  chartIndicator.value = 'Series'
}
</script>

<template>
  <el-container>
    <el-aside width="0px">

    </el-aside>
    <el-container>
      <el-header>

      </el-header>
      <el-main>
        <el-card class="flex-centered" style="width: 400px; height: 450px;" :body-style="{
          width: '100%', height: '80%', padding: '0px',
        }">
          <template #header>
            <div class="card-header" v-if="chartIndicator === 'Series'">
              <div>Package Building Numbers</div>
              <el-button>
                Fetch Data
              </el-button>
            </div>
            <div class="card-header" v-if="chartIndicator === 'Single'">
              <el-icon>
                <Back @click="back" />
              </el-icon>
              <div>{{ receiver.data[index].date }}</div>
              <span>
                <el-radio-group v-model="radio" size="small">
                  <el-radio-button label="Stack" />
                  <el-radio-button label="Table" />
                </el-radio-group>
              </span>

            </div>

          </template>
          <MixedLineBar :data="receiver.data" v-if="chartIndicator === 'Series'" @check="check" />
          <div class="flex-centered" v-if="chartIndicator === 'Single'" style="width: 100%; height: 100%">
            <Table :data="receiver.data[index].data" v-if="radio === 'Table'" />
            <StackedColumn :data="receiver.data[index].data" v-if="radio === 'Stack'" />
          </div>

        </el-card>
      </el-main>
    </el-container>
  </el-container>

</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.flex-centered {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
