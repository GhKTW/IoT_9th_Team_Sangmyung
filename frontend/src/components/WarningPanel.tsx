type Props = {
  hasWarning: boolean;
};

const WarningPanel: React.FC<Props> = ({ hasWarning }) => {
  const panelClass = hasWarning
    ? 'bg-red-50 border-red-400'
    : 'bg-gray-100 border-dashed border-gray-300';

  const iconClass = hasWarning ? 'text-red-500' : 'text-gray-400';

  return (
    <section
      className={`h-full flex items-center gap-5 rounded-2xl border-2 p-6 transition ${panelClass}`}
    >
      {/* 경고 아이콘: 평상시 회색, 이상 시 빨간색 */}
      <div className={`text-5xl ${iconClass}`}>
        <svg
          viewBox="0 0 24 24"
          className="w-14 h-14"
          aria-hidden="true"
          fill="currentColor"
        >
          <path d="M12 2 1 21h22L12 2zm0 5c.55 0 1 .45 1 1v7a1 1 0 1 1-2 0V8c0-.55.45-1 1-1zm0 11a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5z" />
        </svg>
      </div>

      <p className="text-xl font-semibold">
        {hasWarning
          ? '주의! 이상 상태가 감지되었습니다.'
          : '평상시 회색, 주의시 문구띄우기 및 빨간색채워짐'}
      </p>
    </section>
  );
};

export default WarningPanel;
