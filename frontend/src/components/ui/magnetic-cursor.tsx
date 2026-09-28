import { useEffect, useState, type FC, type ReactNode } from 'react';
import gsap from 'gsap';

export interface MagneticCursorProps {
  children: ReactNode;
  isDark?: boolean;
  magneticFactor?: number;
  lerpAmount?: number;
  hoverPadding?: number;
  hoverAttribute?: string;
  cursorSize?: number;
  cursorColor?: string;
  blendMode?: 'difference' | 'exclusion' | 'normal' | 'screen' | 'overlay';
  cursorClassName?: string;
  shape?: 'circle' | 'square' | 'rounded-square';
  disableOnTouch?: boolean;
  speedMultiplier?: number;
  maxScaleX?: number;
  maxScaleY?: number;
  contrastBoost?: number;
}

export const MagneticCursor: FC<MagneticCursorProps> = ({
  children,
  magneticFactor = 0.25,
  hoverAttribute = 'data-magnetic',
  disableOnTouch = true,
}) => {
  const [isTouchDevice] = useState(() => 
    typeof window !== 'undefined' && ('ontouchstart' in window || (navigator.maxTouchPoints ?? 0) > 0)
  );

  useEffect(() => {
    if (disableOnTouch && isTouchDevice) return;

    const cleanupFunctions: (() => void)[] = [];
    const magneticElements = gsap.utils.toArray<HTMLElement>(`[${hoverAttribute}]`);

    magneticElements.forEach((el) => {
      const xTo = gsap.quickTo(el, 'x', { duration: 0.8, ease: 'elastic.out(1, 0.3)' });
      const yTo = gsap.quickTo(el, 'y', { duration: 0.8, ease: 'elastic.out(1, 0.3)' });

      let rafId: number | null = null;
      const handlePointerMove = (event: PointerEvent) => {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
          const { clientX, clientY } = event;
          const { height, width, left, top } = el.getBoundingClientRect();
          const centerX = left + width / 2;
          const centerY = top + height / 2;
          const offsetX = (clientX - centerX) * magneticFactor;
          const offsetY = (clientY - centerY) * magneticFactor;

          xTo(offsetX);
          yTo(offsetY);
          rafId = null;
        });
      };

      const handlePointerLeave = () => {
        if (rafId) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        xTo(0);
        yTo(0);
      };

      el.addEventListener('pointermove', handlePointerMove);
      el.addEventListener('pointerleave', handlePointerLeave);
      el.addEventListener('pointerout', handlePointerLeave);

      cleanupFunctions.push(() => {
        el.removeEventListener('pointermove', handlePointerMove);
        el.removeEventListener('pointerleave', handlePointerLeave);
        el.removeEventListener('pointerout', handlePointerLeave);
      });
    });

    return () => {
      cleanupFunctions.forEach((cleanup) => cleanup());
    };
  }, [disableOnTouch, isTouchDevice, hoverAttribute, magneticFactor]);

  return <>{children}</>;
};

