/// Ảnh xám thu nhỏ cho bám vết, tạo trên luồng chính ở MỌI khung camera (rẻ: chỉ đọc kênh Y).
///
/// Thu nhỏ bằng trung bình khối f x f (như cv2.INTER_AREA của bản desktop), f = round(rộng / 640).
library;

import 'dart:typed_data';

import 'package:camera/camera.dart';

import '../core/template_tracker.dart';

GrayImage grayFromCameraImage(CameraImage img, {required bool rotate180}) {
  final bgra = img.format.group == ImageFormatGroup.bgra8888;
  return grayFromPlane(img.planes[0].bytes, img.width, img.height, img.planes[0].bytesPerRow,
      bgra: bgra, rotate180: rotate180);
}

/// [plane]: kênh Y (YUV420/NV21, 1 byte/pixel) hoặc BGRA (4 byte/pixel).
GrayImage grayFromPlane(Uint8List plane, int width, int height, int rowStride,
    {bool bgra = false, bool rotate180 = false}) {
  final f = (width / workW).round().clamp(1, 8);
  final ow = width ~/ f, oh = height ~/ f;
  final out = Float32List(ow * oh);
  final inv = 1.0 / (f * f);
  var o = 0;
  if (f == 2 && !bgra) {
    // trường hợp thường gặp (1280x720 -> 640x360): cộng số nguyên 2x2
    for (var oy = 0; oy < oh; oy++) {
      final r0 = 2 * oy * rowStride, r1 = r0 + rowStride;
      for (var ox = 0; ox < ow; ox++) {
        final x = 2 * ox;
        out[o++] = (plane[r0 + x] + plane[r0 + x + 1] + plane[r1 + x] + plane[r1 + x + 1]) * 0.25;
      }
    }
  } else {
    for (var oy = 0; oy < oh; oy++) {
      for (var ox = 0; ox < ow; ox++) {
        var sum = 0.0;
        for (var dy = 0; dy < f; dy++) {
          final row = (oy * f + dy) * rowStride;
          for (var dx = 0; dx < f; dx++) {
            final x = ox * f + dx;
            if (bgra) {
              final i = row + x * 4;
              sum += 0.114 * plane[i] + 0.587 * plane[i + 1] + 0.299 * plane[i + 2];
            } else {
              sum += plane[row + x];
            }
          }
        }
        out[o++] = sum * inv;
      }
    }
  }
  if (rotate180) {
    // xoay 180° = đảo ngược mảng phẳng (giống tiền xử lý YOLO khi cảm biến lắp ngược)
    for (var i = 0, j = out.length - 1; i < j; i++, j--) {
      final tmp = out[i];
      out[i] = out[j];
      out[j] = tmp;
    }
  }
  return GrayImage(ow, oh, out);
}
