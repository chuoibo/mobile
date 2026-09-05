import type { ReactNode } from "react";
import type { StyleProp, ViewStyle } from "react-native";

import { EmptyState } from "./EmptyState";

export interface ErrorStateProps {
  /** What failed, in the product's words; never a raw server code. */
  title?: string;
  /** Why (when known and useful) and what happens to what the person typed. */
  body?: string;
  onRetry: () => void;
  retrying?: boolean;
  /** «Về danh sách», «Dùng lại bản nháp»… */
  secondary?: { label: string; onPress: () => void };
  illustration?: ReactNode;
  layout?: "full" | "inline";
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * Failure that keeps what the person typed. The retry is an outline button so
 * it never competes with the screen's primary action, and the body says out
 * loud that nothing was lost -- twelve screens used to say «Thử lại» with no
 * sentence about the form they were about to keep or discard.
 */
export function ErrorState({
  title = "Chưa đọc được từ máy chủ",
  body = "Kiểm tra mạng rồi thử lại. Những gì bạn đã nhập vẫn còn nguyên.",
  onRetry,
  retrying,
  secondary,
  illustration,
  layout = "inline",
  style,
  testID,
}: ErrorStateProps) {
  return (
    <EmptyState
      kind="failure"
      title={title}
      body={body}
      action={{ label: "Thử lại", onPress: onRetry, loading: retrying }}
      secondary={secondary}
      illustration={illustration}
      layout={layout}
      style={style}
      testID={testID ?? "error-state"}
    />
  );
}
