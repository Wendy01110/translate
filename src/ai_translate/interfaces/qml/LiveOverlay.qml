import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: root

    property string metadataText: ""
    property string sourceText: ""
    property string translationText: ""
    property real desiredHeight: card.implicitHeight

    signal stopRequested()

    Theme { id: theme }

    title: "AI Translate · 实时翻译"
    width: 720
    height: desiredHeight
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.Tool

    function present() {
        root.show()
        root.raise()
    }

    Rectangle {
        id: card
        anchors.fill: parent
        implicitHeight: content.implicitHeight + 30
        color: theme.surface
        radius: 12
        border.width: 1
        border.color: theme.borderStrong

        ColumnLayout {
            id: content
            anchors.fill: parent
            anchors.leftMargin: 24
            anchors.rightMargin: 18
            anchors.topMargin: 16
            anchors.bottomMargin: 14
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Image {
                    source: "icons/app.svg"
                    sourceSize.width: 25
                    sourceSize.height: 25
                    Layout.preferredWidth: 25
                    Layout.preferredHeight: 25
                }

                Label {
                    text: "实时 OCR"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }

                Label {
                    Layout.fillWidth: true
                    text: root.metadataText
                    color: theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    font.family: theme.fontFamily
                    font.pixelSize: 13
                }

                AppButton {
                    objectName: "stopButton"
                    text: "停止"
                    iconSource: "icons/stop.svg"
                    implicitWidth: 86
                    implicitHeight: 36
                    onClicked: root.stopRequested()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: theme.border
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 18
                rowSpacing: 10
                visible: root.sourceText.length > 0 || root.translationText.length > 0

                Label {
                    text: "原文"
                    visible: root.sourceText.length > 0
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }

                Label {
                    Layout.fillWidth: true
                    text: root.sourceText
                    visible: root.sourceText.length > 0
                    color: theme.textPrimary
                    wrapMode: Text.WordWrap
                    font.family: theme.fontFamily
                    font.pixelSize: 14
                    lineHeight: 1.28
                    lineHeightMode: Text.ProportionalHeight
                }

                Label {
                    text: "译文"
                    visible: root.translationText.length > 0
                    color: theme.textSecondary
                    font.family: theme.fontFamily
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }

                Label {
                    Layout.fillWidth: true
                    text: root.translationText
                    visible: root.translationText.length > 0
                    color: theme.textPrimary
                    wrapMode: Text.WordWrap
                    font.family: theme.fontFamily
                    font.pixelSize: 16
                    lineHeight: 1.28
                    lineHeightMode: Text.ProportionalHeight
                }
            }
        }
    }
}
