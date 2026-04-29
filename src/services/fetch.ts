const request = async (url: string, options: RequestInit): Promise<Response> => {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  const contentType = response.headers.get('content-type')
  const streamContentTypes = [
    'text/event-stream',
    'application/octet-stream',
    'application/x-ndjson',
    'text/plain',
    'text/markdown',
  ]
  const isStreamResponse = contentType && (
    streamContentTypes.some(type => contentType.includes(type))
  )

  if (!isStreamResponse) {
    try {
      const jsonResponse = await response.json()
      return jsonResponse
    } 
    catch (err) {
      throw new Error('服务器返回了非流响应')
    }
  }

  return response
}

export default request