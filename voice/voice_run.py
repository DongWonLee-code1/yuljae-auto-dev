#!/usr/bin/env python3
"""
부동산 상담 통화 녹음 화자분리 전사 및 분석 시스템
Real Estate Consultation Call Transcription with Speaker Diarization + Analysis

Usage:
    python -m voice.voice_run input.m4a
    python -m voice.voice_run input.m4a --output-format json
    python -m voice.voice_run input.m4a --with-timestamps
    python -m voice.voice_run input.m4a --analyze  # 분석 포함
    python -m voice.voice_run input.m4a --analyze --no-transcribe  # 기존 텍스트 분석만
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Settings
from voice.assemblyai_client import AssemblyAIClient
from voice.formatters import OutputFormatter


def speech_to_text(
    file_path: str,
    include_timestamps: bool = False,
    output_format: str = "both",
    output_dir: str | None = None,
    analyze: bool = False,
) -> dict:
    """
    음성 파일을 화자 분리와 함께 텍스트로 변환 (선택적 분석 포함)

    Args:
        file_path: 오디오 파일 경로
        include_timestamps: 타임스탬프 포함 여부
        output_format: 출력 형식 ("json", "text", "both")
        output_dir: 출력 디렉토리
        analyze: 분석 엔진 실행 여부

    Returns:
        dict: {
            "result": TranscriptionResult,
            "output_paths": List[str],
            "readable_text": str,
            "analysis": AnalysisResult (if analyze=True)
        }
    """
    settings = Settings()
    if output_dir:
        settings.output_dir = output_dir

    client = AssemblyAIClient(settings)
    result = client.transcribe_file(file_path)

    formatter = OutputFormatter(settings.output_dir)
    output_paths = formatter.save(
        result,
        output_format=output_format,
        with_timestamps=include_timestamps,
    )

    if include_timestamps:
        readable_text = result.to_timestamped_text()
    else:
        readable_text = result.to_readable_text()

    response = {
        "result": result,
        "output_paths": output_paths,
        "readable_text": readable_text,
    }

    if analyze:
        from analysis.analyzer import ConsultationAnalyzer

        analyzer = ConsultationAnalyzer()
        analysis_result = analyzer.analyze(result)
        analysis_paths = analyzer.save_result(analysis_result, settings.output_dir)
        response["analysis"] = analysis_result
        response["output_paths"].extend(analysis_paths)

    return response


def main():
    parser = argparse.ArgumentParser(
        description="부동산 상담 통화 녹음 화자분리 전사 및 분석 시스템"
    )
    parser.add_argument("input_file", help="입력 오디오 파일 경로 (.m4a, .mp3, .wav 등)")
    parser.add_argument(
        "--output-format",
        choices=["json", "text", "both"],
        default="both",
        help="출력 형식 (기본값: both)",
    )
    parser.add_argument(
        "--with-timestamps",
        action="store_true",
        help="텍스트 출력에 타임스탬프 포함",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="출력 디렉토리 (기본값: outputs/)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="전사 후 자동으로 분석 엔진 실행",
    )

    args = parser.parse_args()

    print(f"처리 중: {args.input_file}")

    try:
        output = speech_to_text(
            file_path=args.input_file,
            include_timestamps=args.with_timestamps,
            output_format=args.output_format,
            output_dir=args.output_dir,
            analyze=args.analyze,
        )

        result = output["result"]

        print(f"\n완료! 출력 파일:")
        for path in output["output_paths"]:
            print(f"  - {path}")

        print(f"\n=== 전사 미리보기 (처음 5개 발화) ===")
        for utt in result.utterances[:5]:
            if args.with_timestamps:
                print(f'[{utt.start_formatted}] {utt.speaker_label}: "{utt.text}"')
            else:
                print(f'{utt.speaker_label}: "{utt.text}"')

        if len(result.utterances) > 5:
            print(f"... 외 {len(result.utterances) - 5}개 발화")

        print(f"\n총 시간: {result.duration_formatted}")
        print(f"화자 수: {result.speaker_count}")

        if args.analyze and "analysis" in output:
            analysis = output["analysis"]
            print("\n" + "=" * 50)
            print("=== 분석 결과 요약 ===")
            print("=" * 50)
            print(f"상담 ID: {analysis.consultation_id}")
            print(f"요약: {analysis.summary}")

            if analysis.price.sale_price or analysis.price.jeonse_price:
                print(f"\n[가격] 매매: {analysis.price.sale_price or '-'} / 전세: {analysis.price.jeonse_price or '-'}")

            if analysis.location.district or analysis.location.neighborhood:
                print(f"[위치] {analysis.location.district or ''} {analysis.location.neighborhood or ''} {analysis.location.complex_name or ''}")

            if analysis.timeline.move_in_date or analysis.timeline.contract_date_preference:
                print(f"[일정] 계약: {analysis.timeline.contract_date_preference or '-'} / 입주: {analysis.timeline.move_in_date or '-'}")

            if analysis.negotiation.must_have_conditions:
                print(f"[필수조건] {', '.join(analysis.negotiation.must_have_conditions)}")

            if analysis.customer.family_composition or analysis.customer.age_group:
                print(f"[고객정보] {analysis.customer.age_group or '-'} / {analysis.customer.family_composition or '-'}")

            if analysis.follow_up_needed:
                print(f"\n⚠️  후속 조치 필요: {', '.join(analysis.follow_up_actions)}")

    except FileNotFoundError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"전사 오류: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
