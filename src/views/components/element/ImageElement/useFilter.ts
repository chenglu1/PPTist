import { computed, type Ref } from 'vue'
import type { ImageElementFilters, ImageElementFilterKeys } from '@/types/slides'

export default (filters: Ref<ImageElementFilters | undefined>, isTemplateImage?: Ref<boolean | undefined>) => {
  const normalizedFilters = computed(() => {
    if (!filters.value) return undefined
    if (!isTemplateImage?.value) return filters.value

    const keys = Object.keys(filters.value) as ImageElementFilterKeys[]
    const isPlaceholderFilter = keys.includes('grayscale') && keys.every(key => key === 'grayscale' || key === 'opacity')
    if (!isPlaceholderFilter) return filters.value

    const { grayscale, ...restFilters } = filters.value
    if (!Object.keys(restFilters).length) return undefined
    return restFilters
  })

  const filter = computed(() => {
    if (!normalizedFilters.value) return ''
    let filter = ''
    const keys = Object.keys(normalizedFilters.value) as ImageElementFilterKeys[]
    for (const key of keys) {
      filter += `${key}(${normalizedFilters.value[key]}) `
    }
    return filter
  })

  return {
    filter,
  }
}