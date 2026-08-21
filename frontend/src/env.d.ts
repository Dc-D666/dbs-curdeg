/// <reference types="vite/client" />

/** 构建时注入的部署时间（UTC ISO 字符串，vite.config.ts define） */
declare const __BUILD_TIME__: string

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
