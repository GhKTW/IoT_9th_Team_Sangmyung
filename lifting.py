from sensors import *

# 초기화
# 아마 메인에 전부 모아 두고 호출 안할수도
setup_loadcell()

# 변수
line_checked = False
lift_successful = False

# 1. 이동 중에 주기적으로 호출되며 라인트레이서가 선을 인식하는지 확인하는 함수
def check_line():
    # 라인트레이서 센서 값 읽기 (셋 중 어느것이라도 인식하면 추적 시작)
    line_values = get_line_values()
    if (line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1):
        # 추적 알고리즘 구현

        # 라인트레이서가 세개 다 검은색을 인식하면 목적지 도착

        if (line_values[0] == 1 and line_values[1] == 1 and line_values[2] == 1):
            line_checked = True
    else:
        return

# 2. 들어올리기 시도하는 함수
def attempt_lift():
    # 가운데 거리센서 값 읽어서 물체가 있는지 확인

    # 특정 높이만큼 들기
        # 물체가 있으면 일단 들기 조금 시도(모터를 짧게 작동)

        # 조금 들고 로드셀 값 읽기(한계 무게 초과인지를 계속 확인)
        # 한계 무게 초과하면 모터 작동 멈추고 내려놓기, 조기종료
        lift_successful = False
        return

    # 끝까지 들면 들기 성공 플래그 셋
    lift_successful = True

# 3. 내려놓기 함수
def place down():
    # check_line() 함수로 목적지 도착 확인 후 실행

    # 모터를 반대 방향으로 작동시켜 물체를 천천히 내림

    # 물체가 완전히 내려졌는지 확인(로드셀 값이 기준값인지 확인)

# 4. 들어올릴때 전체 동작 함수
# 이동 중 호출
def go_to_lift():
    # 라인트레이서로 목적지까지 이동
    # check_line() 주기적으로 호출
    check_line()
    if (line_checked):
        # 목적지 도착하면 attempt_lift() 호출
        attempt_lift()
        if (lift_successful):
            # 180도 회전하기 함수 호출
            return True
        elif(not lift_successful):
            # 180도 회전하기 함수 호출
            return False
    else:
        return
    
# 5. 내려놓기 전체 동작 함수
def go_to_place():
    # 라인트레이서로 목적지까지 이동
    # check_line() 주기적으로 호출
    check_line()
    if (line_checked):
        # 목적지 도착하면 place_down() 호출
        place_down()
        # 180도 회전하기 함수 호출
        return
    else:
        # 180도 회전하기 함수 호출
        return