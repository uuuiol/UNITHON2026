/**
 * client.ts와 mock.ts가 같이 던지는 에러 타입.
 *
 * client.ts는 mock.ts를 import 하므로(mockResponse), ApiError를 client.ts
 * 안에 두면 mock.ts가 되돌아 import 할 수 없다(순환 참조). 그래서 둘 다
 * 기대지 않는 이 파일에 따로 둔다.
 */
export class ApiError extends Error {
  // 생성자 파라미터 프로퍼티는 erasableSyntaxOnly 에서 막히므로 필드로 따로 둔다.
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
