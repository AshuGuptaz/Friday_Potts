"use client";

import dynamic from "next/dynamic";

const Spline = dynamic(() => import("@splinetool/react-spline"), {
  ssr: false,
  loading: () => <div className="w-full h-full" />,
});

interface SplineOrbProps {
  scene: string;
  appState?: string;
  className?: string;
}

export function SplineOrb({ scene, className = "" }: SplineOrbProps) {
  return (
    <div className={`w-full h-full ${className}`}>
      <Spline scene={scene} className="w-full h-full" />
    </div>
  );
}
