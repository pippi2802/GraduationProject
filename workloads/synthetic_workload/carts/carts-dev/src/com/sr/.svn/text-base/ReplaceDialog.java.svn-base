/* This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

//ReplaceDialog.java - uses the similar methods as the search class but allows the user to replace
//search strings. The user can also do a replace all.
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.sr;

import java.awt.event.ActionListener;
import java.awt.event.ActionEvent;
import java.awt.event.ItemListener;
import java.awt.event.ItemEvent;
import java.awt.event.KeyEvent;
import java.awt.event.KeyAdapter;

import java.awt.FlowLayout;
import java.awt.Dimension;
import java.awt.BorderLayout;
import java.awt.GridBagLayout;
import java.awt.GridBagConstraints;
import java.awt.Color;

import javax.swing.JComboBox;
import javax.swing.JPanel;
import javax.swing.JCheckBox;
import javax.swing.JLabel;
import javax.swing.JButton;
import javax.swing.JDialog;
import javax.swing.JTextField;
import javax.swing.Box;
import javax.swing.BorderFactory;
import javax.swing.BoxLayout;

import com.jpe.jpe;
import com.jpe.Constants;
import com.utils.*;

public class ReplaceDialog extends JDialog implements ActionListener,
		ItemListener, Constants {

	public ReplaceDialog(jpe window) {
		// Call the base constructor to create a non-modal dialog
		super(window, "Search and Replace", false);

		this.window = window;
		this.setResizable(false);

		jcheck = new JCheckBox("Ignor case");
		jcheck.addItemListener(this);
		jcheck.setFont(SYSTEM_FONT);

		jcheck2 = new JCheckBox("Whole word");
		jcheck2.addItemListener(this);
		jcheck2.setFont(SYSTEM_FONT);

		jcheck3 = new JCheckBox("Wrap");
		jcheck3.addItemListener(this);
		jcheck3.setFont(SYSTEM_FONT);

		JPanel topbutPanel = new JPanel();
		topbutPanel.setLayout(new FlowLayout(FlowLayout.LEFT));
		// topbutPanel.add(jbtFind = createButton("Find"));
		topbutPanel.add(jbtNext = createButton("Find Next"));
		topbutPanel.add(jbtReplace = createButton("Replace"));
		topbutPanel.add(jbtAll = createButton("All"));

		JPanel botbutPanel = new JPanel();
		botbutPanel.setLayout(new FlowLayout(FlowLayout.LEFT));
		botbutPanel.add(Cancel = createButton("Exit"));
		botbutPanel.add(jcheck);
		botbutPanel.add(jcheck2);
		// botbutPanel.add(jcheck3);

		// jbtFind.setToolTipText("Find Word");
		jbtReplace.setToolTipText("Replace Word");
		jbtNext.setToolTipText("Find Next Word");
		jbtAll.setToolTipText("Replace All Words");
		Cancel.setToolTipText("Close Window");

		// Create the dialog button panel
		JPanel buttonPane = new JPanel();
		buttonPane.setLayout(new BoxLayout(buttonPane, BoxLayout.Y_AXIS));
		buttonPane.add(Box.createVerticalGlue());
		buttonPane.add(topbutPanel);
		buttonPane.add(Box.createVerticalGlue());
		buttonPane.add(botbutPanel);
		getContentPane().add(buttonPane, BorderLayout.SOUTH);

		// Code to create the data input panel...
		JPanel dataPane = new JPanel();
		dataPane.setBorder(BorderFactory.createCompoundBorder(BorderFactory
				.createLineBorder(Color.black), BorderFactory
				.createEmptyBorder(5, 5, 5, 5)));
		GridBagLayout gbLayout = new GridBagLayout();
		dataPane.setLayout(gbLayout);
		GridBagConstraints constraints = new GridBagConstraints();

		JLabel findlabel = new JLabel("   Find..              ");
		JLabel replacelabel = new JLabel("                      ..Replace with");

		findlabel.setFont(SYSTEM_FONT);
		replacelabel.setFont(SYSTEM_FONT);

		JPanel Labels = new JPanel();
		Labels.setLayout(new FlowLayout(FlowLayout.CENTER));
		Labels.add(findlabel);
		Labels.add(replacelabel);
		getContentPane().add(Labels, BorderLayout.NORTH);

		JPanel txtField = new JPanel();
		txtField.add(jcb = new JComboBox());
		txtField.add(jcb2 = new JComboBox());
		gbLayout.setConstraints(txtField, constraints);
		dataPane.add(txtField);

		jcb.setFont(SYSTEM_FONT);
		jcb2.setFont(SYSTEM_FONT);

		jcb.setEditable(true);
		jcb.setPreferredSize(new Dimension(130, 18));

		jtf = new JTextField();
		KeyHandler handler = new KeyHandler();
		jtf = (JTextField) jcb.getEditor().getEditorComponent();
		jtf.addKeyListener(handler);

		jcb2.setEditable(true);
		jcb2.setPreferredSize(new Dimension(130, 18));

		jtf2 = new JTextField();
		jtf2 = (JTextField) jcb2.getEditor().getEditorComponent();

		getContentPane().add(dataPane, BorderLayout.CENTER);
		pack();
		setVisible(false);
		setFont(SYSTEM_FONT);

		ignoreCase = false;

		findstr = " ";
		findstr2 = " ";
		wrap = true;
		replaceAll = false;

	}

	void disableRep() {
		jbtReplace.setEnabled(false);
	}

	JButton createButton(String label) {
		JButton button = new JButton(label);
		button.setFont(SYSTEM_FONT);
		button.setPreferredSize(new Dimension(80, 18));
		button.addActionListener(this);
		return button;
	}

	public void getSelectedText() {
		String s = window.getSelectedText();

		if ((s != null) && (s != "")) {
			s.trim();

			int x = jcb.getItemCount();
			int i;
			boolean match = false;

			for (i = 0; i < x; ++i) {
				if (jtf.getText().equals(s)) {
					match = true;
				}
			}

			if (!match) {
				jcb.insertItemAt(makeObj(s), 0);
				jcb.setSelectedIndex(0);
			}

		}
	}

	private Object makeObj(final String item) {
		return new Object() {
			public String toString() {
				return item;
			}
		};
	}

	public void addItemToBox() {

		int x = jcb.getItemCount();
		int i;
		boolean match = false;

		for (i = 0; i < x; ++i) {
			if (jtf.getText().equals(jcb.getItemAt(i).toString())) {
				match = true;
			}
		}

		if (!match) {
			jcb.insertItemAt(makeObj(jtf.getText()), 0);
		}

	}

	public void addItemToBox2() {

		int x = jcb2.getItemCount();
		int i;
		boolean match = false;

		for (i = 0; i < x; ++i) {
			if (jtf2.getText().equals(jcb2.getItemAt(i).toString())) {
				match = true;
			}
		}

		if (!match) {
			jcb2.insertItemAt(makeObj(jtf2.getText()), 0);
		}

	}

	public void itemStateChanged(ItemEvent e) {
		if (jcheck.isSelected()) {
			ignoreCase = true;
		} else {
			ignoreCase = false;
		}

		if (jcheck2.isSelected()) {
			wholeWord = true;
		} else {
			wholeWord = false;
		}

		if (jcheck3.isSelected()) {
			wrap = true;
		} else {
			wrap = false;
		}

	}

	public boolean FindNext() {
		String s, str;
		int a = 0;

		s = window.GetText();

		if (jtf.getText().equals("") || jtf.getText() == null) {
			Utils.userMessage("Nothing to search for", "Nothing to search for",
					2);
			return false;
		} else {
			findstr = jtf.getText();
			addItemToBox();
		}

		if (ignoreCase) {
			s = s.toLowerCase();
			str = findstr.toLowerCase();
		} else {
			str = findstr;
		}

		if (wholeWord) {
			str = " " + str + " ";
		} else {
			str.trim();
		}

		if (str != null) {
			a = str.length();
			pos = s.indexOf(str, window.getCaretPosition());
			window.RequestFocus();

			if (pos == -1) {
				if (wrap) {
					pos = s.indexOf(findstr, 0);
					window.Select(pos, pos + findstr.length());
				} else {
					Utils.userMessage("Not Found", findstr + " not found", 1);
					return false;
				}
			} else {
				window.Select(pos, pos + findstr.length());
			}

			return true;

		} else {
			if (!replaceAll) {
				Utils.userMessage("String not found", "String " + "'" + findstr
						+ "'" + " not found", 2);
			} else {
				Utils.userMessage("Finished", "Search and Replace finished "
						+ new String(Integer.toString(counter))
						+ " occurences replaced.", 2);
				counter = 0;
			}

			return false;
		}

		// return false;

	}

	private void Replace() {

		if (jtf2.getText().equals("") || jtf2.getText() == null) {
			findstr2 = " ";
		} else {
			findstr2 = jtf2.getText();
		}

		String t;

		if (findstr != null) {
			window.RequestFocus();

			t = findstr2;
			if (t != null) {
				try {
					if (wholeWord) {
						window.ReplaceSelection(t);
					} else {
						window.ReplaceSelection(t);
					}
				} catch (Exception ex) {
					System.out.println("Error performing replace: "
							+ ex.getMessage());
					Utils.userMessage("Error",
							"An error has occured, please see error log.", 1);
					Utils.writeErrorLog("Error performing replace "
							+ ex.getMessage());
				}
			}

			if (!replaceAll) {
				FindNext();
				window.RequestFocus();
			}
		}
	}

	private void ReplaceAll() {
		if (window.getSelectedText() == null
				|| window.getSelectedText().equals("")) {
			FindNext();
		}

		while (FindNext()) {
			Replace();
			counter = counter + 1;
		}
	}

	public void actionPerformed(ActionEvent e) {
		Object source = e.getSource();

		if (source == jbtNext) {
			FindNext();
		}

		else if (source == jbtReplace) {
			Replace();
		}

		else if (source == jbtAll) {
			replaceAll = true;

			ReplaceAll();

			replaceAll = false;
		}

		else if (source == Cancel) {
			setVisible(false);
		}

	}

	private jpe window;
	private JButton jbtReplace, jbtNext, jbtAll, Cancel;
	private JTextField jtf, jtf2;
	private String findstr, findstr2;
	private JCheckBox jcheck, jcheck2, jcheck3;
	private boolean ignoreCase, wholeWord, wrap, replaceAll;
	private int pos = 0;
	private int counter = 0;

	private JComboBox jcb, jcb2;

	class KeyHandler extends KeyAdapter {
		public void keyPressed(KeyEvent evt) {
			switch (evt.getKeyCode()) {
			case KeyEvent.VK_ENTER:
				if (evt.getSource() == jtf) {
					FindNext();
				}
			case KeyEvent.VK_ESCAPE:

				setVisible(false);

			}
		}
	}
}
