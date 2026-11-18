/// Ảnh camera (YUV420 / NV21 trên Android, BGRA8888 trên iOS) -> tensor RGB 0..1 letterbox NHWC.
///
/// Lấy mẫu láng giềng gần nhất qua bảng tra chỉ số dựng sẵn (không tạo ảnh RGB trung gian), vừa cắt vùng
/// (xem core/roi.dart), vừa đổi màu, vừa thu nhỏ trong một vòng lặp. Đổi màu bằng số nguyên (hệ số x1024)
/// và bảng tra 0..255 -> 0..1 thay cho phép tính số thực từng điểm ảnh.
library;

import 'dart:typed_data';

import '../core/roi.dart';
import '../core/yolo.dart';

enum PixelFormat { yuv420, nv21, bgra8888 }

/// Một khung ảnh gửi sang isolate xử lý / nhận diện (chỉ chứa dữ liệu thuần, gửi được qua SendPort).
class FramePacket {
  final int width, height; // kích thước bộ đệm (đã là ảnh ngang)
  final PixelFormat format;
  final List<Uint8List> planes;
  final List<int> rowStrides;
  final List<int> pixelStrides;
  final bool rotate180; // cảm biến lắp ngược (sensorOrientation 270)
  FramePacket(this.width, this.height, this.format, this.planes, this.rowStrides, this.pixelStrides,
      this.rotate180);
}

/// 0..255 -> 0..1 (khớp phép chia /255 của bản Python).
final Float32List _unit = Float32List.fromList([for (var i = 0; i < 256; i++) i / 255.0]);

class Preprocessor {
  final int inW, inH;
  late final Float32List input;
  Letterbox? _lb;
  Int32List? _xmap, _ymap;
  bool? _rot;
  CropRect? _crop;
  int _srcW = 0, _srcH = 0;

  Preprocessor(this.inW, this.inH) {
    input = Float32List(inW * inH * 3);
  }

  /// Letterbox của vùng cắt: hộp giải mã ra ở tọa độ vùng cắt, cộng crop.x / crop.y để về khung gốc.
  Letterbox get letterbox => _lb!;

  void _prepare(int w, int h, bool rot, CropRect c) {
    if (_lb != null && _srcW == w && _srcH == h && _rot == rot && _crop == c) return;
    final lb = Letterbox(c.w, c.h, inW, inH);
    final padChanged = _lb == null || _lb!.newW != lb.newW || _lb!.newH != lb.newH;
    _lb = lb;
    _rot = rot;
    _crop = c;
    _srcW = w;
    _srcH = h;
    // cột/hàng nguồn cho từng cột/hàng đích (tâm pixel, giống cv2.resize INTER_NEAREST xấp xỉ);
    // vùng cắt tính trên ảnh đã xoay đứng, xoay 180° thì lật chỉ số về bộ đệm cảm biến
    _xmap = Int32List(lb.newW);
    for (var x = 0; x < lb.newW; x++) {
      var sx = (c.x + ((x + 0.5) / lb.r).floor()).clamp(c.x, c.x + c.w - 1).clamp(0, w - 1);
      if (rot) sx = w - 1 - sx;
      _xmap![x] = sx;
    }
    _ymap = Int32List(lb.newH);
    for (var y = 0; y < lb.newH; y++) {
      var sy = (c.y + ((y + 0.5) / lb.r).floor()).clamp(c.y, c.y + c.h - 1).clamp(0, h - 1);
      if (rot) sy = h - 1 - sy;
      _ymap![y] = sy;
    }
    if (padChanged) input.fillRange(0, input.length, 114 / 255.0); // nền xám như Ultralytics
  }

  /// [crop] null = cả khung.
  Float32List run(FramePacket f, [CropRect? crop]) {
    _prepare(f.width, f.height, f.rotate180, crop ?? CropRect(0, 0, f.width, f.height));
    final lb = _lb!, xmap = _xmap!, ymap = _ymap!, unit = _unit;
    switch (f.format) {
      case PixelFormat.bgra8888:
        final p = f.planes[0], row = f.rowStrides[0];
        for (var y = 0; y < lb.newH; y++) {
          final srow = ymap[y] * row;
          var o = ((y + lb.top) * inW + lb.left) * 3;
          for (var x = 0; x < lb.newW; x++) {
            final i = srow + xmap[x] * 4;
            input[o++] = unit[p[i + 2]];
            input[o++] = unit[p[i + 1]];
            input[o++] = unit[p[i]];
          }
        }
      case PixelFormat.yuv420:
      case PixelFormat.nv21:
        final yp = f.planes[0], yRow = f.rowStrides[0];
        final Uint8List up, vp;
        final int uvRow, uvPix;
        int uOff = 0, vOff = 0;
        if (f.format == PixelFormat.yuv420 && f.planes.length >= 3) {
          up = f.planes[1];
          vp = f.planes[2];
          uvRow = f.rowStrides[1];
          uvPix = f.pixelStrides.length > 1 ? f.pixelStrides[1] : 1;
        } else {
          // NV21: một mặt phẳng, sau Y là VU xen kẽ
          up = vp = yp;
          uvRow = f.width;
          uvPix = 2;
          vOff = yRow * f.height;
          uOff = vOff + 1;
        }
        for (var y = 0; y < lb.newH; y++) {
          final sy = ymap[y];
          final yr = sy * yRow, uvr = (sy >> 1) * uvRow;
          var o = ((y + lb.top) * inW + lb.left) * 3;
          for (var x = 0; x < lb.newW; x++) {
            final sx = xmap[x];
            final yy = yp[yr + sx];
            final uvi = uvr + (sx >> 1) * uvPix;
            final u = up[uOff + uvi] - 128, v = vp[vOff + uvi] - 128;
            // BT.601 toàn dải: R = Y + 1,402 V; G = Y - 0,344 U - 0,714 V; B = Y + 1,772 U
            var r = yy + ((1436 * v) >> 10);
            var g = yy - ((352 * u + 731 * v) >> 10);
            var b = yy + ((1815 * u) >> 10);
            r = r < 0 ? 0 : (r > 255 ? 255 : r);
            g = g < 0 ? 0 : (g > 255 ? 255 : g);
            b = b < 0 ? 0 : (b > 255 ? 255 : b);
            input[o++] = unit[r];
            input[o++] = unit[g];
            input[o++] = unit[b];
          }
        }
    }
    return input;
  }
}
