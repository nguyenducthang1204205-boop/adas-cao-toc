/// Âm thanh cảnh báo: bíp lặp theo mức (giống AlertManager desktop) + câu nói tiếng Việt khi nâng mức.
library;

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../core/safety.dart';

class AlertPlayer {
  static const intervals = {Risk.danger: 0.28, Risk.warning: 0.9};
  static const phrases = {
    Risk.warning: 'Giữ khoảng cách',
    Risk.danger: 'Nguy hiểm, giảm tốc ngay',
  };
  static const voiceCooldownS = 5.0;

  final _players = <Risk, AudioPlayer>{};
  final _tts = FlutterTts();
  bool _voiceOk = false;
  double _lastBeep = -1e9;
  double _lastVoice = -1e9;
  Risk _prev = Risk.safe;

  Future<void> init() async {
    for (final r in [Risk.warning, Risk.danger]) {
      final p = AudioPlayer();
      try {
        await p.setPlayerMode(PlayerMode.lowLatency);
        await p.setReleaseMode(ReleaseMode.stop);
        await p.setSource(AssetSource('sounds/${r == Risk.danger ? 'danger' : 'warning'}.wav'));
        _players[r] = p;
      } catch (e) {
        // không có thiết bị âm thanh (vd. máy ảo): vẫn cảnh báo bằng màu và giọng nói
        debugPrint('Không nạp được âm cảnh báo $r: $e');
        p.dispose();
      }
    }
    try {
      _voiceOk = await _tts.isLanguageAvailable('vi-VN') == true;
      if (_voiceOk) {
        await _tts.setLanguage('vi-VN');
        await _tts.setSpeechRate(0.55);
        await _tts.awaitSpeakCompletion(false);
      }
    } catch (e) {
      debugPrint('TTS không khả dụng: $e');
      _voiceOk = false;
    }
  }

  bool get voiceAvailable => _voiceOk;

  /// Gọi mỗi khung với mức cảnh báo ổn định; [now] tính bằng giây.
  void update(Risk level, double now, {required bool sound, required bool voice}) {
    final escalated = riskRank(level) > riskRank(_prev);
    _prev = level;
    if (voice && _voiceOk && escalated && now - _lastVoice >= voiceCooldownS) {
      _lastVoice = now;
      _tts.speak(phrases[level]!).catchError((Object e) => debugPrint('TTS lỗi: $e'));
      _lastBeep = now; // nhường chỗ cho câu nói
      return;
    }
    final interval = intervals[level];
    if (!sound || interval == null || now - _lastBeep < interval) return;
    _lastBeep = now;
    _play(level);
  }

  void preview(Risk level) => _play(level);

  /// lowLatency (SoundPool trên Android): resume() phát lại từ đầu; seek() không được hỗ trợ và treo.
  void _play(Risk level) {
    _players[level]?.resume().catchError((Object e) => debugPrint('Không phát được âm cảnh báo: $e'));
  }

  Future<void> dispose() async {
    for (final p in _players.values) {
      await p.dispose();
    }
    await _tts.stop();
  }
}
