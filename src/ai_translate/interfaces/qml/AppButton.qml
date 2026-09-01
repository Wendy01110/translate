import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control

    property string kind: "secondary"
    property url iconSource: ""

    Theme { id: theme }

    implicitHeight: 40
    implicitWidth: Math.max(92, contentRow.implicitWidth + 30)
    leftPadding: 15
    rightPadding: 15
    topPadding: 0
    bottomPadding: 0

    contentItem: RowLayout {
        id: contentRow
        spacing: 8

        Image {
            visible: control.iconSource.toString().length > 0
            source: control.iconSource
            sourceSize.width: 18
            sourceSize.height: 18
            Layout.preferredWidth: visible ? 18 : 0
            Layout.preferredHeight: visible ? 18 : 0
            opacity: control.enabled ? 1 : 0.48
        }

        Text {
            text: control.text
            color: control.kind === "primary" ? "#FFFFFF" : theme.textPrimary
            opacity: control.enabled ? 1 : 0.48
            font.family: theme.fontFamily
            font.pixelSize: 14
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            Layout.alignment: Qt.AlignCenter
        }
    }

    background: Rectangle {
        radius: 8
        color: {
            if (control.kind === "primary") {
                if (!control.enabled) return "#9FC4F5"
                if (control.down) return theme.accentPressed
                if (control.hovered) return theme.accentHover
                return theme.accent
            }
            if (!control.enabled) return "#F6F7F9"
            if (control.down) return "#E9EDF3"
            if (control.hovered) return theme.surfaceMuted
            return theme.surface
        }
        border.color: control.kind === "primary" ? color : (control.activeFocus ? theme.accent : theme.border)
        border.width: 1
    }
}
