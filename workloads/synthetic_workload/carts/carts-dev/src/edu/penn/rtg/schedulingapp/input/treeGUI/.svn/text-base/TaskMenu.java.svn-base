package edu.penn.rtg.schedulingapp.input.treeGUI;

import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;

import javax.swing.JMenuItem;
import javax.swing.JPopupMenu;

/**
 * TaskMenu handles the pop up menu when the user clicks on a Task in the Tree
 * UI
 */
public class TaskMenu extends JPopupMenu implements ActionListener{
	CartsTree m_treeRef;
	private final String edtTask="Edit Task";
	private final String delTask="Remove Task";

	public TaskMenu(CartsTree tree) {
		m_treeRef = tree;
		JMenuItem menuItem;
		menuItem = new JMenuItem(edtTask);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(delTask);
		menuItem.addActionListener(this);
		add(menuItem);
	}

	@Override
	public void actionPerformed(ActionEvent e) {
		JMenuItem source = (JMenuItem) (e.getSource());
		if (source.getText().equals(edtTask)) {
			m_treeRef.editTaskClicked();
		} else if (source.getText().equals(delTask)) {
			m_treeRef.removeTaskClicked();
		}
	}
}
