import { useState } from 'react';
import { mockLanes } from './mock/deviceMock';
import type { Lane } from './mock/deviceMock';
import LightPanel from './components/LightPanel';
import WarningPanel from './components/WarningPanel';
import LaneBoard from './components/LaneBoard';

function App() {
  const [lightOn, setLightOn] = useState(false);
  const [lanes, setLanes] = useState<Lane[]>(mockLanes);

  const handleLaneClick = (id: string) => {
    setLanes(prev =>
      prev.map(lane => {
        if (lane.id !== id) return lane;
        if (lane.status === 'done') {
          return { ...lane, status: 'idle', progress: 0 };
        }
        return { ...lane, status: 'done', progress: 1 };
      }),
    );
  };

  const hasWarning = lanes.some(l => l.status === 'warning');

  return (
    <div className="min-h-screen bg-gray-200 p-6 flex gap-6">
      {/* 왼쪽: 전구 + 경고 */}
      <div className="basis-[40%] flex flex-col gap-6">
        <div className="bg-white rounded-2xl border border-gray-300 shadow-sm p-6 flex-1">
          <LightPanel lightOn={lightOn} onChange={setLightOn} />
        </div>

        <div className="bg-white rounded-2xl border border-gray-300 shadow-sm p-6 flex-1">
          <WarningPanel hasWarning={hasWarning} />
        </div>
      </div>

      {/* 오른쪽: 라인 보드 */}
      <div className="flex-1 bg-white rounded-2xl border border-gray-300 shadow-sm p-6 flex items-center justify-center">
        <LaneBoard lanes={lanes} onLaneClick={handleLaneClick} />
      </div>
    </div>
  );
}

export default App;
