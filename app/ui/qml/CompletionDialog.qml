import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    required property Controller controller
    required property bool dryRun
    signal quitRequested
    parent: Overlay.overlay
    anchors.centerIn: parent
    modal: true
    title: dialog.dryRun ? qsTr("Dry Run Complete") : qsTr("Sorting Complete")
    standardButtons: Dialog.Close
    ColumnLayout {
        Label {
            Layout.preferredWidth: 480
            wrapMode: Text.WordWrap
            text: dialog.dryRun ? qsTr("Preview complete. Check the activity log for filename changes. Turn off Dry run to apply them.") : qsTr("Media sorted and renamed. Check the activity log for details.")
        }
        RowLayout {
            Button {
                text: qsTr("Open Folder")
                onClicked: dialog.controller.openCompletedFolder()
            }
            Button {
                text: qsTr("Open Folder and Quit")
                onClicked: {
                    dialog.controller.openCompletedFolder();
                    dialog.quitRequested();
                }
            }
            Button {
                text: qsTr("Quit")
                onClicked: dialog.quitRequested()
            }
        }
    }
}
