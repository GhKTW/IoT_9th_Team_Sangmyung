export type LaneStatus = 'idle' | 'moving' | 'done' | 'warning';

export interface Lane {
  id: string;
  name: string;
  icon: 'apple' | 'grape' | 'banana';
  status: LaneStatus;
  progress: number; // 0 ~ 1
}

export const mockLanes: Lane[] = [
  { id: 'lane-1', name: '사과 라인', icon: 'apple', status: 'done', progress: 1 },
  { id: 'lane-2', name: '포도 라인', icon: 'grape', status: 'moving', progress: 0.5 },
  { id: 'lane-3', name: '바나나 라인', icon: 'banana', status: 'idle', progress: 0 },
];
