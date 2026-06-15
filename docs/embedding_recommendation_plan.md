# 텍스트 임베딩 기반 추천 — 설계 계획

현재 추천은 **LLM이 생성한 6축 `style_vector`** 로 콘텐츠 매칭을 한다. 이 문서는 그 위에 **텍스트 임베딩**을 추가해
장소·유저를 같은 의미 공간에 두고 ANN으로 매칭하는 추천 파이프라인을 설계한다. (본 문서는 설계, 코드는 후속.)

## 배경 / 제약

- 지금 `PlaceFeature.style_vector`(VECTOR(6))는 `ai_tag`가 gemma3/Gemini로 overview를 읽어 **6축(활동성·계획성·사교성·공간지향·경험지향·소비스타일)을 0~1로 점수화**해 만든다. 추천은 이 6축과 `UserFeature.preference_vector`(VECTOR(6))의 코사인 거리로 ANN을 돈다.
- 한계:
  - **생성 비용**: 장당 ~14초(로컬 gemma3). 1.5만 장 = 하루+.
  - **노이즈/비일관성**: 12B 로컬 모델의 6축 점수는 run마다 흔들리고, 6차원으로 의미가 크게 뭉개진다.
  - **유저 벡터 출처 불명확**: `preference_vector`를 무엇으로 채울지(행동? 설문?)가 미정.
- 임베딩은 이걸 보완한다: **결정론적·고속(ms)·고정보량**. 6축은 *설명·필터·콜드스타트*용으로 **병행 유지**한다(폐기 아님).

## 목표

1. 장소를 **제목+분류+설명**으로 임베딩해 의미 벡터(예: 1024차원)를 저장한다.
2. 유저의 행동(북마크·리뷰)에서 **같은 공간의 유저 벡터**를 만든다.
3. ANN(코사인)으로 "유저 취향과 가까운 장소"를 추천하고, 콜드스타트는 6축/인기로 폴백한다.
4. 6축 추천과 **점수 블렌딩**으로 A/B 비교 가능하게 둔다.

## 전체 구조

```
[장소]  제목 + 분류(cat) + 설명(overview)
          │  임베딩 모델 (인코딩, ms)
          ▼
   place_embedding  (VECTOR(1024))  ──┐
                                       │  CosineDistance + HNSW
[유저]  북마크/리뷰한 장소들             │  (ANN 최근접 검색)
          │  가중평균(최신성·별점)        ▼
          ▼                      추천 후보 Top-N
   user_embedding  (VECTOR(1024)) ──→  필터(지역·태그)·이미본 제외 → 결과
                                       │
          (행동 0이면)  6축/인기 폴백 ──┘
```

핵심: **유저 벡터와 장소 벡터가 같은 임베딩 공간**에 있어야 코사인이 의미를 가진다. 그래서 유저 벡터는 "좋아한 장소 임베딩의 무게중심"으로 만든다.

---

## 1. 장소 임베딩 생성·저장

### 입력 텍스트 구성
한 장소를 다음을 합친 문자열로 인코딩한다(필드 라벨을 붙여 의미를 강화):

```
제목: {place_name}
분류: {lcls_systm1/2/3 라벨}  (예: 자연 > 자연관광지 > 국립공원)
설명: {description}
```

- `description`이 빈 장소는 제목+분류만으로도 인코딩 가능(LLM 태깅과 달리 임베딩은 짧아도 됨) → **현재 미태깅으로 빠지는 overview 없는 장소도 커버**된다.
- 분류 코드(`lcls_systm*`)는 라벨로 풀어 넣는다(`lcls_codes.lcls_label` 재사용).

### 모델 선택 (후보)
| 모델 | 차원 | 비고 |
| --- | --- | --- |
| **BGE-m3** | 1024 | 한국어 강함, 긴 텍스트, 로컬/오프라인 가능 (권장) |
| multilingual-e5-large | 1024 | 다국어, 검증 많음 |
| ko-sroberta-multitask | 768 | 가벼움, 한국어 특화 |
| Gemini / OpenAI 임베딩 API | 768~3072 | 운영 단순(키만), 호출 비용 |

> 결정 필요: **로컬 모델(무료·프라이빗) vs 임베딩 API(운영 단순).** 수집/태깅을 로컬 ollama로 해온 흐름상 **로컬 BGE-m3**를 1순위로 제안.

### 저장 / 인덱스
`PlaceFeature`에 필드 추가(또는 별도 `PlaceEmbedding` 모델):

```python
content_vector = VectorField(dimensions=1024, null=True)

class Meta:
    indexes = [
        HnswIndex(
            name="place_content_vector_hnsw",
            fields=["content_vector"],
            m=16, ef_construction=64,
            opclasses=["vector_cosine_ops"],
        )
    ]
```

> **인덱스는 벡터 대량 적재 후 생성**한다(HNSW는 증분 삽입이 비싸다 — `docs` 인덱스 메모 참고). 즉 임베딩 전부 채운 뒤 `CREATE INDEX`.

### 실행
`ai_tag`와 같은 패턴의 management command(`embed_places`)로:
- `--only-missing`(content_vector 없는 장소만), `--content-type-id`, `--batch-size`
- 임베딩은 **배치 인코딩**이 가능(한 번에 수십~수백 문장) → 태깅보다 훨씬 빠름.

---

## 2. 유저 벡터 구축

### 기본 공식 — 좋아한 장소의 가중평균
```
user_vec = normalize( Σ  wᵢ × place_content_vectorᵢ )
```

### 가중치 wᵢ (신호 강도 × 최신성)
| 신호 (모델) | 가중 |
| --- | --- |
| `Bookmark` | +1.0 |
| `Review` 5★ / 4★ | +1.0 / +0.6 |
| `Review` 3★ | +0.2 |
| `Review` 1~2★ | −0.5 (부정) |
| (선택) 조회 로그 | +0.1 |

- **최신성 감쇠**: `wᵢ ×= exp(−Δ일수 / 90)` — 취향 변화 반영.
- **부정 신호**: 낮은 별점 장소는 빼서 그 방향에서 멀어지게.

### 다중 관심사 문제
산사 + 클럽을 둘 다 좋아하면 단순 평균은 무의미한 중점이 된다. 대응:
- 좋아한 장소 벡터를 **k-means(k=2~3) 군집** → **유저를 여러 벡터로 표현**, 군집별 추천을 섞는다.
- (1차 구현은 단일 평균으로 시작, 데이터 쌓이면 군집화 도입.)

### 저장 / 갱신
- `UserFeature`에 `content_vector = VectorField(1024)` 추가(기존 6축 `preference_vector`와 **공존**).
- 갱신: **Celery `@shared_task`** 로
  - 증분: 북마크/리뷰 생성 시그널 → 해당 유저만 재계산 큐잉, 또는
  - 배치: 야간 beat로 활동 유저 일괄 재계산.

---

## 3. 추천 질의

```python
PlaceFeature.objects
    .annotate(distance=CosineDistance("content_vector", user_vec))
    .filter(place__is_active=True)
    .exclude(place_id__in=user_seen_ids)        # 북마크/이미 본 것 제외
    # 선택: .filter(place__lcls_systm1=region) 등 사전 필터
    .order_by("distance")[:N]
```

### 콜드스타트 / 폴백 (행동 부족)
1. **온보딩 시드**: 가입 시 관심 장소 3개 선택 → 그 임베딩 평균을 초기 `content_vector`.
2. **6축 설문**: 활동성/계획성 슬라이더 → 기존 6축 `preference_vector` 세팅(해석 가능해서 직접 입력에 적합).
3. **인기 폴백(익명/무신호)**: `rating_avg DESC, bookmark_count DESC` (현 익명 로직 재사용).
- 전환 규칙: **북마크 ≥ 5개**면 임베딩 평균으로 전환, 그 전엔 6축/인기.

---

## 4. 6축과의 관계 (병행 전략)

| 용도 | 쓰는 벡터 |
| --- | --- |
| 추천 유사도 매칭 | **임베딩 `content_vector`** (정확·고속) |
| 설명("왜 추천?")·필터·온보딩 슬라이더 | **6축 `style_vector` / `preference_vector`** (해석 가능) |
| 콜드스타트 | 6축 설문 → 임베딩 전환 |

- 초기엔 **점수 블렌딩**으로 비교: `score = α·cos_embed + (1−α)·cos_6축`. α를 0→1로 올리며 품질 관찰.
- 6축 LLM 태깅은 유지하되, 추천 주력은 임베딩으로 이전.

---

## 5. 모델 / 스키마 변경 요약

- `PlaceFeature`(또는 신규 `PlaceEmbedding`): `content_vector VECTOR(1024)` + HNSW(cosine).
- `UserFeature`: `content_vector VECTOR(1024)` 추가(기존 6축과 공존).
- 마이그레이션은 **벡터 채운 뒤 HNSW 인덱스 생성** 순서.

## 6. 구현 로드맵

| 단계 | 목표 | 산출물 |
| :---: | :--- | :--- |
| 1 | 임베딩 모델 PoC | 샘플 50장 인코딩, 코사인 유사도 눈검증(절↔절 가깝나) |
| 2 | 장소 임베딩 파이프라인 | `embed_places` command, `content_vector` 저장, HNSW |
| 3 | 유저 벡터 v1 | 북마크 가중평균 → `UserFeature.content_vector`, Celery 갱신 |
| 4 | 추천 질의 + 폴백 | ANN 뷰, 콜드스타트(6축/인기) 연결 |
| 5 | 블렌딩·평가 | α 블렌딩, 오프라인 지표(아래)로 6축 대비 비교 |
| 6 | 고도화 | 다중관심사 군집화, (데이터 충분 시) two-tower 학습 |

## 7. 평가 방법

- **오프라인**: 유저의 북마크 일부를 가리고(hold-out), 추천이 그걸 맞히는지 — Recall@K / NDCG@K. 6축 vs 임베딩 vs 블렌딩 비교.
- **온라인**: 추천 CTR / 북마크 전환율 A/B.

## 8. 열린 결정사항

- [ ] 임베딩 모델: **로컬 BGE-m3** vs API — 운영/비용 트레이드오프.
- [ ] 저장 위치: `PlaceFeature`에 컬럼 추가 vs 별도 `PlaceEmbedding` 모델.
- [ ] 차원(1024)·HNSW 파라미터(m, ef) 튜닝.
- [ ] 유저 벡터 갱신: 증분 시그널 vs 야간 배치(또는 혼합).
- [ ] 콜드스타트 전환 임계(북마크 N개)와 블렌딩 α 초기값.
