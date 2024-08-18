import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import { motion } from 'framer-motion';
import { CityData, Route, Station } from '../types';
import {
  getOfficialMapConfig,
  getOfficialMapPoint,
  getQuestionFocusPoints
} from '../data/officialMaps';
import { SubwayMap } from './SubwayMap';

interface OfficialMetroMapProps {
  cityData: CityData;
  startStation: Station;
  endStation: Station;
  highlightRoute: Route | null;
}

interface ViewportSize {
  width: number;
  height: number;
}

interface Point {
  x: number;
  y: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function OfficialMetroMap({
  cityData,
  startStation,
  endStation,
  highlightRoute
}: OfficialMetroMapProps) {
  const config = getOfficialMapConfig(cityData.cityId);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<ViewportSize>({ width: 1000, height: 620 });
  const [imageStatus, setImageStatus] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [panOffset, setPanOffset] = useState<Point>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ pointerId: number; start: Point; pan: Point } | null>(null);
  const focusPoints = useMemo(
    () => config ? getQuestionFocusPoints(cityData, startStation, endStation, highlightRoute, config) : [],
    [cityData, startStation, endStation, highlightRoute, config]
  );

  useEffect(() => {
    setImageStatus(config ? 'loading' : 'loaded');
  }, [config?.src]);

  useEffect(() => {
    setPanOffset({ x: 0, y: 0 });
    setIsDragging(false);
    dragStartRef.current = null;
  }, [config?.src, startStation.id, endStation.id, highlightRoute]);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;

    const updateViewport = () => {
      const rect = element.getBoundingClientRect();
      setViewport({ width: rect.width, height: rect.height });
    };

    updateViewport();
    const observer = new ResizeObserver(updateViewport);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  if (!config) {
    return (
      <SubwayMap
        cityData={cityData}
        startStation={startStation}
        endStation={endStation}
        highlightRoute={highlightRoute}
        focusMode={highlightRoute ? 'route' : 'question'}
        className="min-h-[620px] rounded-[28px]"
      />
    );
  }

  if (imageStatus === 'error') {
    return (
      <div className="relative">
        <SubwayMap
          cityData={cityData}
          startStation={startStation}
          endStation={endStation}
          highlightRoute={highlightRoute}
          focusMode={highlightRoute ? 'route' : 'question'}
          className="min-h-[620px] rounded-[28px]"
        />
        <div className="absolute bottom-4 left-4 rounded-2xl bg-amber-100/95 px-4 py-3 text-xs font-black text-amber-700 shadow-lg">
          高清地图暂时没打开，已切换到游戏线路图
        </div>
      </div>
    );
  }

  const startPoint = getOfficialMapPoint(startStation, cityData, config);
  const endPoint = getOfficialMapPoint(endStation, cityData, config);
  const minX = Math.min(...focusPoints.map(point => point.x));
  const maxX = Math.max(...focusPoints.map(point => point.x));
  const minY = Math.min(...focusPoints.map(point => point.y));
  const maxY = Math.max(...focusPoints.map(point => point.y));
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const boxWidth = Math.max(220, maxX - minX);
  const boxHeight = Math.max(180, maxY - minY);
  const fullScale = Math.min(viewport.width / config.width, viewport.height / config.height);
  const focusScale = Math.min(
    viewport.width / (boxWidth + 460),
    viewport.height / (boxHeight + 360)
  );
  const scale = clamp(focusScale, fullScale, fullScale * 3.7);
  const imageWidth = config.width * scale;
  const imageHeight = config.height * scale;
  const minTranslateX = Math.min(0, viewport.width - imageWidth);
  const minTranslateY = Math.min(0, viewport.height - imageHeight);
  const baseTranslateX = clamp(viewport.width / 2 - centerX * scale, minTranslateX, 0);
  const baseTranslateY = clamp(viewport.height / 2 - centerY * scale, minTranslateY, 0);
  const translateX = clamp(baseTranslateX + panOffset.x, minTranslateX, 0);
  const translateY = clamp(baseTranslateY + panOffset.y, minTranslateY, 0);
  const marker = (point: { x: number; y: number }) => ({
    left: point.x * scale + translateX,
    top: point.y * scale + translateY
  });
  const startMarker = marker(startPoint);
  const endMarker = marker(endPoint);
  const routePoints = focusPoints.map(marker);

  const clampPanOffset = (nextPan: Point): Point => ({
    x: clamp(baseTranslateX + nextPan.x, minTranslateX, 0) - baseTranslateX,
    y: clamp(baseTranslateY + nextPan.y, minTranslateY, 0) - baseTranslateY
  });

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (imageStatus !== 'loaded') return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStartRef.current = {
      pointerId: event.pointerId,
      start: { x: event.clientX, y: event.clientY },
      pan: panOffset
    };
    setIsDragging(true);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const dragStart = dragStartRef.current;
    if (!dragStart || dragStart.pointerId !== event.pointerId) return;

    const nextPan = {
      x: dragStart.pan.x + event.clientX - dragStart.start.x,
      y: dragStart.pan.y + event.clientY - dragStart.start.y
    };
    setPanOffset(clampPanOffset(nextPan));
  };

  const stopDragging = (event: PointerEvent<HTMLDivElement>) => {
    if (dragStartRef.current?.pointerId === event.pointerId) {
      dragStartRef.current = null;
      setIsDragging(false);
    }
  };

  return (
    <div
      ref={viewportRef}
      className={`relative h-[62vh] min-h-[560px] touch-none overflow-hidden rounded-[28px] bg-slate-100 shadow-inner ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDragging}
      onPointerCancel={stopDragging}
      onLostPointerCapture={() => {
        dragStartRef.current = null;
        setIsDragging(false);
      }}
    >
      <motion.img
        src={config.src}
        alt={config.title}
        className="absolute left-0 top-0 max-w-none select-none"
        draggable={false}
        onLoad={() => setImageStatus('loaded')}
        onError={() => setImageStatus('error')}
        animate={{
          width: imageWidth,
          height: imageHeight,
          x: translateX,
          y: translateY
        }}
        transition={{ type: 'spring', stiffness: 120, damping: 24 }}
      />

      {imageStatus === 'loading' && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/82 backdrop-blur-sm">
          <div className="rounded-3xl bg-white px-6 py-5 text-center shadow-xl">
            <div className="mx-auto mb-3 h-10 w-10 animate-spin rounded-full border-4 border-teal-100 border-t-teal-500" />
            <div className="text-base font-black text-slate-700">高清地图正在展开</div>
            <div className="mt-1 text-sm font-bold text-slate-400">马上聚焦到本题区域</div>
          </div>
        </div>
      )}

      {highlightRoute && routePoints.length > 1 && (
        <svg className="pointer-events-none absolute inset-0 h-full w-full">
          <polyline
            points={routePoints.map(point => `${point.left},${point.top}`).join(' ')}
            fill="none"
            stroke="#facc15"
            strokeWidth="10"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.88"
            style={{ filter: 'drop-shadow(0 0 10px rgba(250, 204, 21, 0.9))' }}
          />
        </svg>
      )}

      <div
        className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
        style={{ left: startMarker.left, top: startMarker.top }}
        title={`起点：${startStation.name}`}
        aria-label={`起点：${startStation.name}`}
      >
        <div className="h-4 w-4 rounded-full border-2 border-white bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.28),0_2px_8px_rgba(15,23,42,0.28)]" />
      </div>

      <div
        className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
        style={{ left: endMarker.left, top: endMarker.top }}
        title={`终点：${endStation.name}`}
        aria-label={`终点：${endStation.name}`}
      >
        <div className="text-xl leading-none text-amber-400 drop-shadow-[0_2px_4px_rgba(15,23,42,0.35)] [-webkit-text-stroke:1.5px_white]">
          ★
        </div>
      </div>

      <div className="absolute bottom-4 left-4 rounded-2xl bg-white/92 px-4 py-3 text-xs font-bold text-slate-500 shadow-lg">
        真实高清图参考 · 已聚焦本题区域
      </div>
    </div>
  );
}
