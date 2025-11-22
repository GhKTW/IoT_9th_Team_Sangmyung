type Props = {
  lightOn: boolean;
  onChange: (value: boolean) => void;
};

const LightPanel: React.FC<Props> = ({ lightOn, onChange }) => {
  return (
    <section className="h-full flex items-center gap-10">
      {/* 전구 아이콘 */}
      <div className="flex-1 flex justify-center">
        <div
          className={`text-7xl transition-all ${
            lightOn ? 'text-yellow-400 drop-shadow-[0_0_12px_rgba(250,204,21,0.9)]' : 'text-gray-400'
          }`}
        >
          💡
        </div>
      </div>

      {/* on / off 버튼 */}
      <div className="flex flex-col gap-4">
        <button
          className={`w-32 text-2xl font-semibold rounded-lg border-2 py-2 transition
            ${
              lightOn
                ? 'border-green-300 bg-green-50 text-green-600'
                : 'border-green-300 bg-white text-green-600'
            }`}
          onClick={() => onChange(true)}
        >
          on
        </button>

        <button
          className={`w-32 text-2xl font-semibold rounded-lg border-2 py-2 transition
            ${
              !lightOn
                ? 'border-red-300 bg-red-50 text-red-600'
                : 'border-red-300 bg-white text-red-600'
            }`}
          onClick={() => onChange(false)}
        >
          off
        </button>
      </div>
    </section>
  );
};

export default LightPanel;
