"""모델 목록 조회 또는 작은 해석 요청만 수행. 설치 실행 기능 없음."""
import argparse
from installone.haigpt import Gateway, GatewayError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", action="store_true", help="공식 계정별 LLM ID 목록 조회")
    args = parser.parse_args()
    try:
        gateway = Gateway()
        if args.models:
            models = gateway.models()
            print("HaiGPT 인증 및 모델 목록 조회 확인 (텍스트 생성은 아직 미확인)")
            for model in models:
                print(model)
        else:
            plan = gateway.interpret("1번 PC에 Python 실습환경 설치해 줘", {"1": {}})
            if plan.seats != ("1",) or plan.profile != "python-lab":
                raise GatewayError("연결 응답의 해석 결과가 테스트 요청과 다릅니다.")
            print("HaiGPT 실제 연결·해석 검증 완료 / 대상: 1번 / 프로필: python-lab / 설치 실행 없음 / VM 미검증")
        return 0
    except GatewayError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
