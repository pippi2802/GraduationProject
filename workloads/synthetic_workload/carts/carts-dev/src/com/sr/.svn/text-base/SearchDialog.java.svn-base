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

// SearchDialog.java -  displays a search dialog box using JDialog and allows the user
//to search for a string (case sensitive).
//The class uses the indexOf() method of the String class to find the specified string.
//The position of the search string is returned - the length of the search string is added
//to this position and these two co-ordinates are passed to the highlight method of the text
//component to highlight the search string.
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
import java.awt.Font;

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

import com.utils.*;
import com.jpe.jpe;
import com.jpe.Constants;

public class SearchDialog extends JDialog implements ActionListener,
		ItemListener, Constants {
	// Constructor
	public SearchDialog(jpe window) {
		// Call the base constructor to create a non-modal dialog
		super(window, "Find", false);

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
		topbutPanel.add(jbtNext = createButton("Find Next"));
		topbutPanel.add(jbtCancel = createButton("Exit"));

		jbtNext.setToolTipText("Find Next Word");
		jbtCancel.setToolTipText("Close Window");

		JPanel botbutPanel = new JPanel();
		botbutPanel.setLayout(new FlowLayout(FlowLayout.LEFT));
		botbutPanel.add(jcheck);
		botbutPanel.add(jcheck2);
		botbutPanel.add(jcheck3);

		// Create and add the buttons to the buttonPane
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

		JLabel findlabel = new JLabel("Find");
		findlabel.setFont(new Font("Arial", 0, 12));
		JPanel Labels = new JPanel();
		Labels.setLayout(new FlowLayout(FlowLayout.CENTER));
		Labels.add(findlabel);

		getContentPane().add(Labels, BorderLayout.NORTH);

		JPanel txtField = new JPanel();

		txtField.add(jcb = new JComboBox());
		jcb.setFont(SYSTEM_FONT);
		gbLayout.setConstraints(txtField, constraints);
		dataPane.add(txtField);

		jcb.setEditable(true);
		jcb.setPreferredSize(new Dimension(175, 18));
		jtf = new JTextField();
		KeyHandler handler = new KeyHandler();
		jtf = (JTextField) jcb.getEditor().getEditorComponent();
		jtf.addKeyListener(handler);

		getContentPane().add(dataPane, BorderLayout.CENTER);
		pack();
		setVisible(false);
		setFont(SYSTEM_FONT);
		ignoreCase = false;

	}

	public void selectText() {
		jtf.selectAll();
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

	JButton createButton(String label) {
		JButton button = new JButton(label);
		button.setFont(SYSTEM_FONT);
		button.setPreferredSize(new Dimension(80, 18));
		button.addActionListener(this);
		return button;
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

	public void FindNext() {
		String s;
		findstr = "";
		// get editor text
		s = window.GetText();

		// get search string
		if (jtf.getText().equals("")) {
			return;
		} else {
			findstr = jtf.getText();
			addItemToBox();
		}

		if (ignoreCase) {
			s = s.toLowerCase();
			findstr = findstr.toLowerCase();
		}

		if (wholeWord) {
			findstr = " " + findstr + " ";
		} else {
			findstr.trim();
		}

		// get the caret position
		pos = s.indexOf(findstr, window.getCaretPosition());

		if (pos == -1) {
			if (wrap) {
				pos = s.indexOf(findstr, 0);
				if (pos != -1) {
					window.Select(pos, pos + findstr.length());
				} else {
					Utils.userMessage("Not Found", findstr + " not found", 1);
				}
			} else {
				Utils.userMessage("Not Found", findstr + " not found", 1);
			}
		} else {
			window.Select(pos, pos + findstr.length());
		}
	}

	public void actionPerformed(ActionEvent e) {
		if (e.getSource() instanceof JButton) {
			if (e.getSource() == jbtNext) {
				FindNext();
			} else if (e.getSource() == jbtCancel) {
				setVisible(false);
			}
		}
	}

	private jpe window;
	private JButton jbtNext, jbtCancel;
	private JTextField jtf;
	private JComboBox jcb;
	private String findstr;
	private JCheckBox jcheck, jcheck2, jcheck3;
	private boolean ignoreCase, wholeWord, wrap;
	private int pos = -1;
	private Utils Utils;

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
