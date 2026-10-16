// 네이버 블로그 에디터(SmartEditor ONE) 위치 정보
//
// 네이버가 화면 구조를 바꾸면 자동 입력이 멈춘다. 그때는 이 파일만 고치면 된다.
// 각 항목은 후보 목록이고, 앞에서부터 처음 찾히는 것을 쓴다.

module.exports = {
  writeUrl: 'https://blog.naver.com/GoBlogWrite.naver',
  // 글쓰기 화면이 들어 있는 iframe (없으면 페이지 자체에서 찾는다)
  editorFrameUrl: /PostWriteForm\.naver/,

  // 처음 열 때 뜨는 팝업
  // 주의: has-text("취소")는 툴바의 "취소선" 버튼까지 잡는다. 팝업 안에서 글자가 정확히 같은 버튼만 찾을 것
  draftPopupCancel: ['.se-popup-button-cancel', '.se-popup button:text-is("취소")'],
  helpPanelClose: ['.se-help-panel-close-button', 'button[class*="help"][class*="close"]'],

  title: ['.se-documentTitle .se-text-paragraph', '.se-title-text', '.se-section-documentTitle'],
  bodyFirstParagraph: ['.se-component.se-text:not(.se-documentTitle) .se-text-paragraph'],
  // 제목을 뺀 본문 블록
  bodyComponent: '.se-component:not(.se-documentTitle)',

  toolbar: {
    image: ['button.se-image-toolbar-button', 'button[data-name="image"]'],
    divider: ['button.se-horizontal-line-toolbar-button', 'button[data-name="horizontal-line"]'],
    quotation: ['button.se-insert-quotation-default-toolbar-button', 'button.se-quotation-toolbar-button', 'button[data-name="quotation"]'],
    // 본문 / 소제목 글자 스타일
    textFormat: ['button.se-text-format-toolbar-button', 'button[data-name="text-format"]'],
    textFormatHeading: ['button.se-toolbar-option-text-format-sectionTitle-button', '[data-value="sectionTitle"]', 'button:text-is("소제목")'],
    textFormatBody: ['button.se-toolbar-option-text-format-text-button', '[data-value="text"]', 'button:text-is("본문")'],
    // 가운데 정렬
    // 정렬 버튼은 현재 정렬에 따라 class가 바뀌므로 data-name으로 찾는다
    align: ['button[data-name="align-drop-down-with-justify"]', 'button.se-property-toolbar-drop-down-button[class*="se-align-"]'],
    alignCenter: ['button.se-toolbar-option-align-center-button', 'button[data-value="center"]', 'button[class*="align-center"]'],
  },

  imageComponent: '.se-component.se-image',
  imageCaption: '.se-caption .se-text-paragraph, .se-module-text.se-caption',

  // 상단 저장 / 발행
  saveButton: ['button[class*="save_btn"]', 'button:text-is("저장")'],
  // 저장 버튼 옆 숫자 (임시저장 글 개수)
  saveCount: 'button[class*="save_count_btn"]',
  publishButton: ['button[class*="publish_btn"]', 'button:text-is("발행")'],
  // 발행 설정 패널
  tagInput: ['#tag-input', 'input[placeholder*="태그"]'],
  publishConfirm: ['button[class*="confirm_btn"]', 'button[data-testid="seOnePublishBtn"]'],
  // 전체공개 (라디오 버튼은 숨겨져 있어서 글자 라벨을 누른다)
  publicRadio: ['label[for="open_public"]', 'label:text-is("전체공개")'],
};
