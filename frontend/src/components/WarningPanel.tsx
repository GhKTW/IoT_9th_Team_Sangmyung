import React from 'react';

// Props 타입 정의: message는 선택적(optional) prop으로 설정합니다.
type Props = {
  message?: string;
};

const WarningPanel: React.FC<Props> = ({ message }) => {
  // message가 존재하면 경고 상태로 판단합니다.
  const hasWarning = !!message;

  // 경고 상태에 따라 스타일을 다르게 적용합니다.
  const panelClass = hasWarning
      ? 'bg-red-100 border-red-400 text-red-700' // 경고 시: 붉은색 계열
      : 'bg-gray-100 border-gray-300 text-gray-500'; // 평상시: 회색 계열

  const iconClass = hasWarning ? 'text-red-500' : 'text-gray-400';

  return (
      <section
          className={`flex items-center p-4 border-2 rounded-lg shadow-sm transition-colors duration-300 ${panelClass}`}
      >
        {/* 경고 아이콘 */}
        <div className={`flex-shrink-0 mr-4 ${iconClass}`}>
          <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-10 h-10"
          >
            <path
                fillRule="evenodd"
                d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z"
                clipRule="evenodd"
            />
          </svg>
        </div>
        {/* 메시지 표시 영역 */}
        <div>
          <h3 className="text-lg font-semibold mb-1">
            {hasWarning ? '경고 시스템 알림' : '시스템 정상 가동 중'}
          </h3>
          <p className="text-sm font-medium">
            {message || '현재 감지된 이상 상태가 없습니다.'}
          </p>
        </div>
      </section>
  );
};

export default WarningPanel;