// IoT_9th_Team_Sangmyung/frontend/src/App.tsx

import { useState, useEffect } from 'react';
import axios from 'axios';
import WarningPanel from './components/WarningPanel';

// 센서 데이터 타입 정의
interface SensorData {
    distance: number;
    lightLevel: number;
    weight: number; // NOTE: 이 값은 0.0 ~ 100.0 (%) 사이의 백분율 값입니다.
    isOverloaded: boolean;
    isLightOn: boolean;
    detectedObject: string;
    status: string;
}

// 프로세스 맵 컴포넌트: 적재장 -> 이동 -> 하역장 시각화
const ProcessMap = ({ status, objectName }: { status: string; objectName: string }) => {
    // 현재 물건이 무엇인지 (apple, banana, grape)
    const isApple = objectName.includes('apple') || objectName.includes('사과');
    const isBanana = objectName.includes('banana') || objectName.includes('바나나');
    const isGrape = objectName.includes('grape') || objectName.includes('포도');

    // 상태별 활성화 여부 판단
    // 1. 적재 중: LIFTING 상태일 때
    const isLoading = status === 'LIFTING' || status === 'WEIGHING';

    // 2. 이동 중: TRANSPORTING 상태일 때
    const isMoving = status === 'TRANSPORTING' || status === 'MOVING';

    // 3. 하역 중/완료: UNLOADING, DROP, ARRIVED 상태일 때
    const isUnloading = status === 'UNLOADING' || status === 'DROP' || status === 'ARRIVED';

    return (
        <div className="bg-white p-8 rounded-2xl shadow-lg border border-gray-100 mb-8">
            <h2 className="text-2xl font-bold mb-8 text-gray-800 flex items-center">
                <span className="bg-blue-100 text-blue-600 p-2 rounded-lg mr-3">🗺️</span>
                실시간 작업 진행도
            </h2>

            <div className="flex items-center justify-between relative px-4">

                {/* [STEP 1] 적재장 (Loading Zone) */}
                <div className={`flex flex-col items-center z-10 p-4 rounded-xl transition-all duration-500 ${isLoading ? 'bg-blue-50 scale-110 shadow-md ring-2 ring-blue-200' : 'bg-transparent'}`}>
                    <span className="text-gray-500 font-bold mb-3 text-lg">📥 적재장</span>
                    <div className="flex gap-2">
                        {/* 물건 아이콘들: 해당 물건을 들 때만 불이 켜짐 */}
                        <FruitIcon type="🍎" active={isLoading && isApple} label="사과" />
                        <FruitIcon type="🍌" active={isLoading && isBanana} label="바나나" />
                        <FruitIcon type="🍇" active={isLoading && isGrape} label="포도" />
                    </div>
                </div>

                {/* [STEP 2] 이동 게이지 (Progress Bar) */}
                <div className="flex-1 mx-8 relative h-4 bg-gray-200 rounded-full overflow-hidden">
                    {/* 이동 중일 때 파란색 바가 애니메이션으로 움직임 */}
                    {isMoving && (
                        <div className="absolute top-0 left-0 h-full w-full bg-blue-500 animate-progress origin-left"></div>
                    )}
                    {/* 배경 화살표 */}
                    <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-gray-300 text-2xl tracking-[1em] font-bold">
                        ➤➤➤
                    </div>
                </div>

                {/* [STEP 3] 하역장 (Unloading Zone) */}
                <div className={`flex flex-col items-center z-10 p-4 rounded-xl transition-all duration-500 ${isUnloading ? 'bg-green-50 scale-110 shadow-md ring-2 ring-green-200' : 'bg-transparent'}`}>
                    <span className="text-gray-500 font-bold mb-3 text-lg">🏁 하역장</span>
                    <div className="flex gap-2">
                        {/* 물건 아이콘들: 하역할 때 불이 켜짐 */}
                        <FruitIcon type="🍎" active={isUnloading && isApple} label="사과" />
                        <FruitIcon type="🍌" active={isUnloading && isBanana} label="바나나" />
                        <FruitIcon type="🍇" active={isUnloading && isGrape} label="포도" />
                    </div>
                </div>

            </div>

            {/* 상태 텍스트 표시 */}
            <div className="text-center mt-8 font-semibold text-gray-500">
                {isLoading && <span className="text-blue-600 animate-pulse">🏗️ 물건을 들어올리는 중입니다...</span>}
                {isMoving && <span className="text-blue-600 animate-pulse">🚚 하역장으로 이동 중입니다...</span>}
                {isUnloading && <span className="text-green-600 animate-pulse">✅ 도착! 하역 작업을 진행합니다.</span>}
                {!isLoading && !isMoving && !isUnloading && <span>⏳ 대기 중...</span>}
            </div>
        </div>
    );
};

// 작은 과일 아이콘 컴포넌트
const FruitIcon = ({ type, active}: { type: string, active: boolean, label: string }) => (
    <div className={`flex flex-col items-center transition-all duration-300 ${active ? 'opacity-100 scale-125' : 'opacity-20 grayscale'}`}>
        <span className={`text-3xl ${active ? 'drop-shadow-md' : ''}`}>{type}</span>
    </div>
);

function App() {
    const [data, setData] = useState<SensorData | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                // 실제 API 엔드포인트에서 데이터 통신
                const response = await axios.get('http://localhost:8080/api/sensor/current');
                setData(response.data);
            } catch (error) {
                console.error('데이터 통신 에러:', error);
            }
        };
        const interval = setInterval(fetchData, 1000);
        return () => clearInterval(interval);
    }, []);

    const getStatusMessage = (status: string) => {
        switch (status) {
            case 'SEARCHING': return '🔍 물체 탐색 중';
            case 'LIFTING': return '🏗️ 적재 중 (Lifting)';
            case 'WEIGHING': return '⚖️ 무게 측정 중';
            case 'TRANSPORTING': return '🚚 운송 중 (Moving)';
            case 'UNLOADING': return '⬇️ 하역 중 (Dropping)';
            case 'ARRIVED': return '🏁 작업 완료';
            case 'OVERLOAD': return '⚠️ 과적 경고!';
            default: return '대기 중';
        }
    };

    // data.weight는 이제 kg이 아닌 백분율 (0.0 ~ 100.0)입니다.
    const warningMessage = data?.isOverloaded
        ? `⚠️ 무게 초과 (${data.weight.toFixed(1)}%)! 작업을 중단합니다.`
        : undefined;

    const currentObject = data?.detectedObject?.toLowerCase() || '';

    // 백분율 값을 0~100 사이로 안전하게 제한
    const weightPercentage = Math.min(Math.max(data?.weight || 0, 0), 100);
    // 게이지 색상 결정: 80% (OVERLOAD_WARNING_THRESHOLD) 초과 시 빨간색
    const gaugeColorClass = data?.isOverloaded
        ? 'bg-red-500'
        : 'bg-gradient-to-r from-blue-400 to-blue-600';


    return (
        // 배경색을 밝은 톤(bg-gray-50)으로 변경
        <div className="min-h-screen bg-gray-50 p-8 font-sans text-gray-800">
            <header className="mb-10 text-center">
                <h1 className="text-4xl font-extrabold text-gray-900 mb-2 tracking-tight">
                    🚜 스마트 지게차 관제 시스템
                </h1>
                <p className="text-gray-500">Smart Forklift Dashboard</p>
            </header>

            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* 1. 경고 패널 (WarningPanel.tsx는 그대로 유지) */}
                <div className="lg:col-span-2">
                    <WarningPanel message={warningMessage} />
                </div>

                {/* 2. [NEW] 프로세스 맵 (지도 대신 들어감) */}
                <div className="lg:col-span-2">
                    <ProcessMap status={data?.status || ''} objectName={currentObject} />
                </div>

                {/* 3. 화물 적재 현황 (요청하신 기능 유지) */}
                <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100 flex flex-col justify-center">
                    <h2 className="text-xl font-bold mb-6 text-gray-800">📦 화물 적재 현황</h2>
                    <div className="flex justify-around items-center">

                        {/* 사과 - 붉은색 테두리와 그림자 효과 */}
                        <div className={`flex flex-col items-center transition-all duration-500 ${currentObject.includes('apple') || currentObject.includes('사과') ? 'opacity-100 scale-110' : 'opacity-20 grayscale'}`}>
                            <div className="w-24 h-24 rounded-full bg-red-50 border-4 border-red-400 flex items-center justify-center text-5xl shadow-xl">
                                🍎
                            </div>
                            <span className="mt-3 font-bold text-red-500 text-lg">사과</span>
                        </div>

                        {/* 바나나 - 노란색 테두리와 그림자 효과 */}
                        <div className={`flex flex-col items-center transition-all duration-500 ${currentObject.includes('banana') || currentObject.includes('바나나') ? 'opacity-100 scale-110' : 'opacity-20 grayscale'}`}>
                            <div className="w-24 h-24 rounded-full bg-yellow-50 border-4 border-yellow-400 flex items-center justify-center text-5xl shadow-xl">
                                🍌
                            </div>
                            <span className="mt-3 font-bold text-yellow-500 text-lg">바나나</span>
                        </div>

                        {/* 포도 - 보라색 테두리와 그림자 효과 */}
                        <div className={`flex flex-col items-center transition-all duration-500 ${currentObject.includes('grape') || currentObject.includes('포도') ? 'opacity-100 scale-110' : 'opacity-20 grayscale'}`}>
                            <div className="w-24 h-24 rounded-full bg-purple-50 border-4 border-purple-400 flex items-center justify-center text-5xl shadow-xl">
                                🍇
                            </div>
                            <span className="mt-3 font-bold text-purple-500 text-lg">포도</span>
                        </div>
                    </div>
                </div>

                {/* 4. 상태 정보 패널들 */}
                <div className="grid grid-cols-1 gap-6">

                    {/* 작업 상태 & 조명 */}
                    <div className="grid grid-cols-2 gap-6">
                        <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100 flex flex-col items-center justify-center">
                            <h2 className="text-lg font-bold mb-2 text-gray-500">현재 상태</h2>
                            <div className="text-2xl font-bold text-blue-600 text-center break-keep">
                                {getStatusMessage(data?.status || '')}
                            </div>
                        </div>

                        <div className={`p-6 rounded-2xl shadow-lg border flex flex-col items-center justify-center transition-all ${data?.isLightOn ? 'bg-yellow-50 border-yellow-300' : 'bg-white border-gray-100'}`}>
                            <h2 className="text-lg font-bold mb-2 text-gray-500">조명 상태</h2>
                            <div className={`text-5xl mb-1 ${data?.isLightOn ? 'text-yellow-500 drop-shadow-md' : 'text-gray-300'}`}>
                                {data?.isLightOn ? '💡' : '⚫'}
                            </div>
                            <div className={`font-bold ${data?.isLightOn ? 'text-yellow-600' : 'text-gray-400'}`}>
                                {data?.isLightOn ? 'ON' : 'OFF'}
                            </div>
                        </div>
                    </div>

                    {/* 적재 무게 게이지 (요청에 따라 퍼센트로 변경됨) */}
                    <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100">
                        <div className="flex justify-between items-end mb-3">
                            <h2 className="text-lg font-bold text-gray-800">현재 적재 무게</h2>
                            <span className={`text-3xl font-bold ${data?.isOverloaded ? 'text-red-500' : 'text-blue-600'}`}>
                                {weightPercentage.toFixed(1)} <span className="text-xl text-gray-400">%</span>
                            </span>
                        </div>
                        {/* 게이지 바 */}
                        <div className="w-full bg-gray-100 rounded-full h-6 overflow-hidden shadow-inner">
                            <div
                                className={`h-full transition-all duration-700 ease-out ${gaugeColorClass}`}
                                style={{ width: `${weightPercentage}%` }} // 백분율 값 사용
                            >
                                {/* 빗금 무늬 효과 (CSS) */}
                                <div className="w-full h-full opacity-30" style={{ backgroundImage: 'linear-gradient(45deg,rgba(255,255,255,.15) 25%,transparent 25%,transparent 50%,rgba(255,255,255,.15) 50%,rgba(255,255,255,.15) 75%,transparent 75%,transparent)', backgroundSize: '1rem 1rem' }}></div>
                            </div>
                        </div>
                        <div className="flex justify-between text-xs text-gray-400 mt-2 font-medium">
                            <span>0%</span>
                            <span>80% (경고)</span>
                            <span>100% (최대)</span>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}

export default App;