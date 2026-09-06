/**
 * Axios 实例封装。
 * 所有后端请求通过此模块发出，后续各业务模块直接 import api。
 */

import axios from 'axios'

const BASE_URL = 'http://localhost:8003'

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export default api
