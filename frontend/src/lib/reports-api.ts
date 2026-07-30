import { api } from './api-client'

async function downloadFile(url: string, filename: string) {
  const response = await api.get(url, { responseType: 'blob' })
  const blobUrl = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = blobUrl
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(blobUrl)
}

export const reportsApi = {
  downloadClassificationsCsv: () => downloadFile('/reports/classifications/csv', 'classifications.csv'),
  downloadClassificationsExcel: () => downloadFile('/reports/classifications/excel', 'classifications.xlsx'),
  downloadProductsCsv: () => downloadFile('/reports/products/csv', 'products.csv'),
  downloadProductsExcel: () => downloadFile('/reports/products/excel', 'products.xlsx'),
  downloadClassificationPdf: (id: number) =>
    downloadFile(`/reports/classifications/${id}/pdf`, `classification_${id}.pdf`),
}
