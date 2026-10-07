import { useEffect, useRef, type ReactNode } from "react";

interface DetailDrawerProps {
  title: string;
  eyebrow: string;
  onClose: () => void;
  children: ReactNode;
}

export function DetailDrawer({
  title,
  eyebrow,
  onClose,
  children,
}: DetailDrawerProps) {
  const drawerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    drawerRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;

      const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) {
        event.preventDefault();
        drawerRef.current.focus();
      } else if (document.activeElement === drawerRef.current) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus();
    };
  }, [onClose]);

  return (
    <div
      className="drawer-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        ref={drawerRef}
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        tabIndex={-1}
      >
        <header className="drawer-header">
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h2 id="drawer-title">{title}</h2>
          </div>
          <button
            className="drawer-close"
            type="button"
            onClick={onClose}
            aria-label="Close details"
          >
            ×
          </button>
        </header>
        <div className="drawer-content">{children}</div>
      </aside>
    </div>
  );
}
