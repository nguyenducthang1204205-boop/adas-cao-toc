/// Cấu hình (giống adas/config.py + bảng điều kiện đường của adas/safety.py).
library;

const classLabelsVi = {
  'car': 'Ô tô',
  'truck': 'Xe tải',
  'bus': 'Xe khách',
  'Jeepney': 'Xe khách',
  'motorcycle': 'Xe máy',
};

/// Chiều cao / bề rộng thực trung bình (m) - cho ước lượng dự phòng Pinhole.
const realHeightsM = {'car': 1.50, 'truck': 3.00, 'bus': 3.20, 'Jeepney': 2.10, 'motorcycle': 1.25};
const realWidthsM = {'car': 1.80, 'truck': 2.50, 'bus': 2.50, 'Jeepney': 2.00, 'motorcycle': 0.80};

/// Hiệu chỉnh IPM bằng hình chữ nhật trên mặt đường có kích thước biết trước.
/// imagePoints: 4 góc trên ảnh (tỉ lệ 0..1), thứ tự dưới-trái, dưới-phải, trên-phải, trên-trái.
class CalibrationConfig {
  List<List<double>> imagePoints;
  double rectWidthM;
  double rectLengthM;
  double nearDistanceM;
  double laneHalfWidthM;
  double maxRangeM;
  double cameraVfovDeg;

  CalibrationConfig({
    List<List<double>>? imagePoints,
    this.rectWidthM = 3.75,
    this.rectLengthM = 30.0,
    this.nearDistanceM = 6.0,
    this.laneHalfWidthM = 1.9,
    this.maxRangeM = 150.0,
    this.cameraVfovDeg = 55.0,
  }) : imagePoints = imagePoints ?? defaultPoints();

  static List<List<double>> defaultPoints() => [
        [0.33, 0.90],
        [0.67, 0.90],
        [0.535, 0.62],
        [0.465, 0.62],
      ];

  CalibrationConfig copy() => CalibrationConfig.fromJson(toJson());

  Map<String, dynamic> toJson() => {
        'image_points': imagePoints,
        'rect_width_m': rectWidthM,
        'rect_length_m': rectLengthM,
        'near_distance_m': nearDistanceM,
        'lane_half_width_m': laneHalfWidthM,
        'max_range_m': maxRangeM,
        'camera_vfov_deg': cameraVfovDeg,
      };

  factory CalibrationConfig.fromJson(Map<String, dynamic> j) => CalibrationConfig(
        imagePoints: (j['image_points'] as List?)
            ?.map((p) => (p as List).map((v) => (v as num).toDouble()).toList())
            .toList(),
        rectWidthM: _d(j['rect_width_m'], 3.75),
        rectLengthM: _d(j['rect_length_m'], 30.0),
        nearDistanceM: _d(j['near_distance_m'], 6.0),
        laneHalfWidthM: _d(j['lane_half_width_m'], 1.9),
        maxRangeM: _d(j['max_range_m'], 150.0),
        cameraVfovDeg: _d(j['camera_vfov_deg'], 55.0),
      );
}

/// Mức tối thiểu theo luật của từng dải tốc độ (khớp legalGapTable trong safety.dart).
const defaultBandGapsM = [35.0, 55.0, 70.0, 100.0];

/// Chính sách ngưỡng an toàn (xem safety.dart).
class SafetyPolicy {
  final double timeGapS; // quy tắc thời gian, chỉ dùng khi V < 60 km/h
  /// Ngưỡng cảnh báo (đường khô) người dùng đặt cho từng dải của legalGapTable; không thấp hơn luật.
  final List<double> bandGapsM;
  final double weatherFactor;
  final double dangerRatio;
  final double minDistanceM;
  final double ttcWarningS;
  final double ttcDangerS;
  final bool useLegalTable;
  final String condition;
  final double roadMu;
  final double visibilityM;

  const SafetyPolicy({
    this.timeGapS = 2.0,
    this.bandGapsM = defaultBandGapsM,
    this.weatherFactor = 1.0,
    this.dangerRatio = 0.5,
    this.minDistanceM = 5.0,
    this.ttcWarningS = 4.0,
    this.ttcDangerS = 2.0,
    this.useLegalTable = true,
    this.condition = 'Đường khô ráo, tầm nhìn tốt',
    this.roadMu = 0.7,
    this.visibilityM = 0.0,
  });
}

class AlertConfig {
  bool soundEnabled;
  bool voiceEnabled;
  bool onlyEgoLane;
  double escalateSeconds; // mức mới phải kéo dài ngần này giây (>= 2 khung) mới nâng
  double holdSeconds;

  AlertConfig({
    this.soundEnabled = true,
    this.voiceEnabled = true,
    this.onlyEgoLane = true,
    this.escalateSeconds = 0.1,
    this.holdSeconds = 0.8,
  });

  Map<String, dynamic> toJson() => {
        'sound_enabled': soundEnabled,
        'voice_enabled': voiceEnabled,
        'only_ego_lane': onlyEgoLane,
        'escalate_seconds': escalateSeconds,
        'hold_seconds': holdSeconds,
      };

  factory AlertConfig.fromJson(Map<String, dynamic> j) => AlertConfig(
        soundEnabled: j['sound_enabled'] as bool? ?? true,
        voiceEnabled: j['voice_enabled'] as bool? ?? true,
        onlyEgoLane: j['only_ego_lane'] as bool? ?? true,
        escalateSeconds: _d(j['escalate_seconds'], 0.1),
        holdSeconds: _d(j['hold_seconds'], 0.8),
      );
}

class RoadCondition {
  final String key;
  final String name;
  final String shortName;
  final double factor; // hệ số nhân khoảng cách so với đường khô
  final double mu; // hệ số bám ước tính
  final double ttcWarningS;
  final double ttcDangerS;
  final String advice;
  const RoadCondition(this.key, this.name, this.shortName, this.factor, this.mu, this.ttcWarningS,
      this.ttcDangerS, this.advice);
}

/// Hệ số ≈ 0,7/μ (giống ROAD_CONDITIONS của bản desktop).
const roadConditions = <String, RoadCondition>{
  'dry': RoadCondition('dry', 'Đường khô ráo, tầm nhìn tốt', 'Khô ráo', 1.0, 0.70, 4.0, 2.0,
      'Giữ khoảng cách tối thiểu theo bảng quy định.'),
  'wet': RoadCondition('wet', 'Mặt đường ướt, mưa nhỏ', 'Mưa nhỏ', 1.4, 0.50, 5.0, 2.5,
      'Độ bám giảm (hệ số bám ≈ 0,5), quãng phanh dài hơn khoảng 1,4 lần.'),
  'heavy_rain': RoadCondition('heavy_rain', 'Mưa to, mặt đường đọng nước', 'Mưa to', 2.0, 0.35, 6.0,
      3.0, 'Nguy cơ trượt nước (hệ số bám ≈ 0,35): giảm tốc độ, giữ khoảng cách gấp đôi.'),
  'fog': RoadCondition('fog', 'Sương mù, tầm nhìn hạn chế', 'Sương mù', 1.5, 0.60, 5.5, 3.0,
      'Bật đèn sương mù/đèn cốt, giảm tốc để dừng kịp trong phạm vi nhìn thấy.'),
  'slippery': RoadCondition('slippery', 'Mặt đường trơn trượt (dầu, bùn, sỏi)', 'Trơn trượt', 2.5,
      0.25, 6.0, 3.0, 'Độ bám rất thấp (hệ số bám ≈ 0,25): giảm tốc rõ rệt, tránh phanh gấp.'),
};

/// Yếu tố cộng thêm (nhân dồn): (nhãn, nhãn ngắn, hệ số).
const modifiers = <String, (String, String, double)>{
  'night': ('Ban đêm, thiếu ánh sáng', 'Ban đêm', 1.2),
  'heavy_vehicle': ('Xe chủ chở nặng', 'Chở nặng', 1.3),
  'tired': ('Tài xế mệt mỏi', 'Mệt mỏi', 1.15),
};
const maxFactor = 3.0;

double _d(Object? v, double def) => v is num ? v.toDouble() : def;
