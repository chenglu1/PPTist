import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

import 'prosemirror-view/style/prosemirror.css'
import 'animate.css'
import '@/assets/styles/prosemirror.scss'
import '@/assets/styles/global.scss'
import '@/assets/styles/font.scss'

import Directive from '@/directive'

const isNativeDevtoolsShortcut = (event: KeyboardEvent) => {
	const key = event.key.toUpperCase()
	const isWindowsDevtools = event.ctrlKey && event.shiftKey && ['I', 'J', 'C'].includes(key)
	const isMacDevtools = event.metaKey && event.altKey && ['I', 'J', 'C'].includes(key)

	return key === 'F12' || isWindowsDevtools || isMacDevtools
}

document.addEventListener('contextmenu', event => {
	if (event.shiftKey) event.stopImmediatePropagation()
}, true)

document.addEventListener('keydown', event => {
	if (isNativeDevtoolsShortcut(event)) event.stopImmediatePropagation()
}, true)

const app = createApp(App)
app.use(Directive)
app.use(createPinia())
app.mount('#app')
