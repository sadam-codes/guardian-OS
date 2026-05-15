export function captureFrameFromVideo(video, quality = 0.88) {
  if (!video?.videoWidth) return null

  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)

  return new Promise((resolve) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          resolve(null)
          return
        }
        resolve(new File([blob], 'frame.jpg', { type: 'image/jpeg' }))
      },
      'image/jpeg',
      quality,
    )
  })
}
