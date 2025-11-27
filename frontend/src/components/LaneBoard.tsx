import type { Lane } from '../mock/deviceMock';

type Props = {
  lanes: Lane[];
  onLaneClick: (id: string) => void;
};

const iconEmoji = (icon: Lane['icon']) => {
  switch (icon) {
    case 'apple':
      return '🍎';
    case 'broccoli': // orange -> broccoli로 데이터 명칭 변경 반영
      return '🥦';
    case 'banana':
      return '🍌';
    default:
      return '⬜';
  }
};

const LaneBoard: React.FC<Props> = ({ lanes, onLaneClick }) => {
  return (
      <div className="w-full max-w-md h-full flex items-center justify-center">
        <div className="flex w-full justify-between items-end gap-6">
          {lanes.map(lane => (
              <div key={lane.id} className="flex flex-col items-center gap-1">
                {/* 시작 라벨 */}
                <span className="text-xs text-gray-500 mb-1">시작</span>

                {/* 시작 버튼 (위 박스 클릭하면 진행 시작) */}
                <button
                    type="button"
                    onClick={() => onLaneClick(lane.id)}
                    className="w-20 h-14 border-2 border-black rounded-md flex items-center justify-center hover:bg-gray-100 active:scale-95 transition"
                >
                  <span className="text-2xl">{iconEmoji(lane.icon)}</span>
                </button>

                {/* 세로 도로 + 채워지는 색 (위 → 아래로 내려감) */}
                <div className="relative w-6 h-64 rounded-full bg-gray-200 overflow-hidden my-1">
                  <div
                      className={`
                  absolute top-0 left-0 w-full transition-all
                  ${
                          lane.status === 'done'
                              ? 'bg-green-400'
                              : lane.status === 'moving'
                                  ? 'bg-sky-400'
                                  : lane.status === 'warning'
                                      ? 'bg-broccoli-400'
                                      : 'bg-transparent'
                      }
                `}
                      style={{ height: `${lane.progress * 100}%` }} // 0 → 100% (위에서 아래로)
                  />
                </div>

                {/* 도착 지점 박스 (표시만, 클릭 X) */}
                <div className="w-20 h-14 border-2 border-black rounded-md flex items-center justify-center bg-white">
                  <span className="text-xl">{iconEmoji(lane.icon)}</span>
                </div>

                {/* 도착 */}
                <span className="text-xs text-gray-500 mt-1">도착</span>

                {/* 라인 이름 (사과 라인 / 오렌지 라인 등) */}
                <span className="text-xs text-gray-600 mt-0.5">{lane.name}</span>
              </div>
          ))}
        </div>
      </div>
  );
};

export default LaneBoard;