package com.textarea;

/**
 * Find.java - Find/Replace class for use with the Jipe Project.  Copyright
 * (c) 1996-1999 Steve Lawson.  E-Mail steve@e-i-s.co.uk Latest version can be
 * found at http://e-i-s.co.uk/jipe
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

import java.awt.*;
import java.awt.event.*;
import javax.swing.*;
import javax.swing.text.Keymap;

/**
 * This dialog supports the search/replace text functionality.
 * 
 * history 12 July 2000 mgh: set default button for dialog to find_next button
 * and disabled enter key awt compatibility for find text field.
 * 
 */
public class Find extends JDialog implements ActionListener {

	/**
	 * *
	 */
	JPanel jPanel = new JPanel();

	/**
	 * *
	 */
	JButton find_next = new JButton();
	/**      */
	JButton replace = new JButton();
	/**
	 * *
	 */
	JButton replaceAll = new JButton();
	/**      */
	JButton cancel = new JButton();
	/**
	 * *
	 */
	JTextField find = new JTextField();
	/**      */
	JTextField replacewith = new JTextField();
	/**      */
	JLabel jLabel1 = new JLabel();
	/**
	 * *
	 */
	JLabel jLabel2 = new JLabel();
	/**      */
	JCheckBox matchcase = new JCheckBox();
	/**      */
	int pos;
	/**      */
	int count;
	/**
	 * *
	 */
	int a;
	/**      */
	int newcounter;
	/**
	 * *
	 */
	JEditTextArea editor;

	/**
	 * *
	 * 
	 * @param parent
	 * @param text
	 */
	public Find(JFrame parent, JEditTextArea text) {
		super(parent, "Find/Replace", false);
		this.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE);
		this.setLocationRelativeTo(this);
		this.setResizable(false);
		this.setModal(true);

		editor = text;
		find_next.setText("  Find Next  ");
		replace.setText("   Replace  ");
		replaceAll.setText("Replace All");
		cancel.setText("    Cancel    ");
		jLabel1.setText("Find Text:");
		jLabel2.setText("Replace With:");
		matchcase.setText("Match Case");

		JPanel jPanela = new JPanel();
		JPanel jPanelb = new JPanel();
		JPanel jPanelc = new JPanel();
		JPanel jPaneld = new JPanel();
		jPanel.setLayout(new GridLayout(0, 1, 4, 0));
		jPanela.setLayout(new FlowLayout(FlowLayout.RIGHT));
		jPanelb.setLayout(new FlowLayout(FlowLayout.RIGHT));
		jPanelc.setLayout(new FlowLayout(FlowLayout.RIGHT));
		jPaneld.setLayout(new FlowLayout(FlowLayout.RIGHT));
		jPanela.add(jLabel1);
		jPanela.add(find);
		jPanela.add(find_next);
		jPanelb.add(jLabel2);
		jPanelb.add(replacewith);
		jPanelb.add(replace);
		jPanelc.add(replaceAll);
		jPaneld.add(matchcase);
		jPaneld.add(cancel);
		find.setColumns(14);
		replacewith.setColumns(14);

		jPanel.setBorder(BorderFactory.createTitledBorder(""));

		jPanel.add(jPanela);
		jPanel.add(jPanelb);
		jPanel.add(jPanelc);
		jPanel.add(jPaneld);

		getContentPane().add(jPanel);

		find_next.addActionListener(this);
		replace.addActionListener(this);
		replaceAll.addActionListener(this);
		cancel.addActionListener(this);

		setResizable(false);
		pack();

		// disable awt compatibility for find text field so that the enter key
		// will work for default button
		KeyStroke enter = KeyStroke.getKeyStroke(KeyEvent.VK_ENTER, 0);
		Keymap map = find.getKeymap();
		map.removeKeyStrokeBinding(enter);

		getRootPane().setDefaultButton(find_next);
	}

	/**
	 * Method to retrieve and assign user input.
	 * 
	 * @param event
	 */
	public void actionPerformed(ActionEvent event) {
		Object source = event.getSource();
		if (source == cancel) {
			setVisible(false);
		}
		// Replace the Text
		if (source == replace)
			Replace();

		// Find the Text
		if (source == find_next)
			find();

		// Find & Replace all text in one operation.
		if (source == replaceAll)
			replaceAll();

	}

	/**
	 * Method to search through text, and then hi-light results.
	 * 
	 */
	public void find() {
		String str;
		String txt;
		count = 0;
		a = 0;
		if (matchcase.isSelected()) {
			txt = editor.getText();
			str = find.getText();
		} else {
			txt = editor.getText().toLowerCase();
			str = find.getText().toLowerCase();
		}
		pos = txt.indexOf(str, editor.getSelectionEnd() + newcounter);
		if (pos >= 0)
			editor.select(pos, pos + str.length());
		else {
			pos = txt.indexOf(str, 0);
			if (pos >= 0)
				editor.select(pos, pos + str.length());
		}
	}

	/**
	 * Method to replace text using results/hilighted text from the find method.
	 * 
	 */
	public void Replace() {
		int start = editor.getSelectionStart();
		int end = editor.getSelectionEnd();
		if (end > start)
			editor.setSelectedText(replacewith.getText());
		editor.select(start, start + replacewith.getText().length());
		find();
	}

	/**
	 * Method to ensure that the Find Next button has focus when this dialog box
	 * is open.
	 * 
	 * @param visible
	 */
	public void setVisible(boolean visible) {
		super.setVisible(visible);

		if (visible) {
			find.requestFocus();
			find.setCaretPosition(0);
			find.moveCaretPosition(find.getText().length());
		}
	}

	/**
	 * Method to replace all occurences of the find method, using a loop through
	 * the replace method to achive this.
	 * 
	 */
	public void replaceAll() {
		editor.select(0, 0);
		while (pos >= 0)
			Replace();
	}
}
