package edu.penn.rtg.schedulingapp.input.treeGUI.dialog;

import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JDialog;
import javax.swing.JPanel;
import javax.swing.JTextField;

import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.input.treeGUI.CartsTree;
import edu.penn.rtg.schedulingapp.util.UserUtil;

import java.beans.*;
import java.awt.*;
import java.awt.event.*;

/**
 * AddTaskDialog handles the dialog to add new Task to the Scheduling Tree
 */
@SuppressWarnings("serial")
public class AddTaskDialog extends JDialog implements ActionListener,
		PropertyChangeListener {
	private final String labName="Task Name";
	private final String labP="Period";
	private final String labE="Execution";
	private final String labD="Deadline";
	private final String labDelta_rel = "Delta_rel";
	private final String labDelta_sch = "Delta_sch";
	private final String labDelta_cxs = "Delta_cxs";
	private final String labDelta_crpmd = "Delta_crpmd";

	protected CartsTree dialogParent;
	protected JTextField nameField;
	protected NumericTextField periodField, executionField, deadlineField;
	protected NumericTextField delta_rel_field, delta_cxs_field, delta_sch_field, delta_crpmd_field;
	protected NumericTextField jitterField,offsetField;
	protected NumericTextField csField;

	protected JOptionPane optionPane;

	protected String btnString1 = "OK";
	protected String btnString2 = "Cancel";
	protected String mode;

	public AddTaskDialog(CartsTree parent) {
		mode="ADD";
		this.dialogParent = parent;
		String title = "New Task";
		this.setDefaultCloseOperation(DISPOSE_ON_CLOSE);
		setTitle(title);
		makeInputField();
		postDialogAction();
		pack();
	}


	private void makeInputField()
	{
		String msg="Provide details of the task";
		String optMsg="----- [Optinal field ] -----";

		JLabel tempLabel;

		tempLabel = new JLabel(labName);
		nameField = new JTextField();
		JPanel namePanel = new JPanel(new GridLayout(1, 2));
		namePanel.add(tempLabel);
		namePanel.add(nameField);

		tempLabel = new JLabel(labP);
		periodField = new NumericTextField();
		JPanel periodPanel = new JPanel(new GridLayout(1, 2));
		periodPanel.add(tempLabel);
		periodPanel.add(periodField);

		tempLabel = new JLabel(labE);
		executionField = new NumericTextField();
		JPanel executionPanel = new JPanel(new GridLayout(1, 2));
		executionPanel.add(tempLabel);
		executionPanel.add(executionField);

		tempLabel = new JLabel(labD);
		deadlineField = new NumericTextField();
		JPanel deadlinePanel = new JPanel(new GridLayout(1, 2));
		deadlinePanel.add(tempLabel);
		deadlinePanel.add(deadlineField);

		tempLabel = new JLabel("Critical Section Length");
		csField = new NumericTextField();
		JPanel csPanel = new JPanel(new GridLayout(1, 2));
		csPanel.add(tempLabel);
		csPanel.add(csField);

		tempLabel = new JLabel("Jitter");
		jitterField = new NumericTextField();
		JPanel panelJitter = new JPanel(new GridLayout(1, 2));
		panelJitter.add(tempLabel);
		panelJitter.add(jitterField);

		tempLabel = new JLabel("Offset");
		offsetField = new NumericTextField();
		JPanel panelOffset = new JPanel(new GridLayout(1, 2));
		panelOffset.add(tempLabel);
		panelOffset.add(offsetField);

		//============Overhead===========//
		tempLabel = new JLabel(labDelta_rel);
		delta_rel_field = new NumericTextField();
		JPanel delta_rel_panel = new JPanel(new GridLayout(1, 2));
		delta_rel_panel.add(tempLabel);
		delta_rel_panel.add(delta_rel_field);
		
		tempLabel = new JLabel(labDelta_sch);
		delta_sch_field = new NumericTextField();
		JPanel delta_sch_panel = new JPanel(new GridLayout(1, 2));
		delta_sch_panel.add(tempLabel);
		delta_sch_panel.add(delta_sch_field);
		
		tempLabel = new JLabel(labDelta_cxs);
		delta_cxs_field = new NumericTextField();
		JPanel delta_cxs_panel = new JPanel(new GridLayout(1, 2));
		delta_cxs_panel.add(tempLabel);
		delta_cxs_panel.add(delta_cxs_field);
		
		tempLabel = new JLabel(labDelta_crpmd);
		delta_crpmd_field = new NumericTextField();
		JPanel delta_crpmd_panel = new JPanel(new GridLayout(1, 2));
		delta_crpmd_panel.add(tempLabel);
		delta_crpmd_panel.add(delta_crpmd_field);
		
		
		

		Object[] array = { msg
				,namePanel 
				,periodPanel
				,executionPanel 
				,deadlinePanel
				,optMsg
				,csPanel
				,panelJitter 
				,panelOffset 
				//====overhead====//
				,delta_rel_panel
				,delta_cxs_panel
				,delta_sch_panel
				,delta_crpmd_panel
		};

		Object[] options = { btnString1, btnString2 };

		optionPane = new JOptionPane(array, JOptionPane.PLAIN_MESSAGE,
				JOptionPane.YES_NO_OPTION, null, options, options[0]);



	}
	private void postDialogAction()
	{
		this.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE);
		this.setLocationRelativeTo(this);
		this.setResizable(false);
		this.setModal(true);



		setContentPane(optionPane);
		// Handle window closing correctly.
		setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);
		addWindowListener(new WindowAdapter() {
			public void windowClosing(WindowEvent we) {
				/*
				 * Instead of directly closing the window, we're going to change
				 * the JOptionPane's value property.
				 */
				optionPane.setValue(new Integer(JOptionPane.CLOSED_OPTION));
			}
		});

		// Ensure the text field always gets the first focus.
		addComponentListener(new ComponentAdapter() {
			public void componentShown(ComponentEvent ce) {
				nameField.requestFocusInWindow();
			}
		});

		// Register an event handler that reacts to option pane state changes.
		optionPane.addPropertyChangeListener(this);

	}

	public void actionPerformed(ActionEvent e) {

	}

	/** This method reacts to state changes in the option pane. */
	public void propertyChange(PropertyChangeEvent e) {
		String prop = e.getPropertyName();

		if (isVisible()
				&& (e.getSource() == optionPane)
				&& (JOptionPane.VALUE_PROPERTY.equals(prop) || JOptionPane.INPUT_VALUE_PROPERTY
						.equals(prop))) {
			Object value = optionPane.getValue();

			if (value == JOptionPane.UNINITIALIZED_VALUE) {
				return;
			}

			optionPane.setValue(JOptionPane.UNINITIALIZED_VALUE);

			if (btnString1.equals(value)) {
				clickBtnOk();
			} else {
				this.dispose();
			}
		}
	}
	public void clickBtnOk()
	{
		String nameStr = new String(nameField.getText());
		String periodStr = new String(periodField.getText());
		String executionStr = new String(executionField.getText());
		String deadlineStr = new String(deadlineField.getText());
		String jitterStr = new String(jitterField.getText());
		String offsetStr = new String(offsetField.getText());
		String csStr=new String(csField.getText());
		String delta_rel_str = new String(delta_rel_field.getText());
		String delta_sch_str = new String(delta_sch_field.getText());
		String delta_cxs_str = new String(delta_cxs_field.getText());
		String delta_crpmd_str = new String(delta_crpmd_field.getText());
		
		if (nameStr.isEmpty()) {
			UserUtil.showErr(labName+" is emptry!");
			return;
		}

		if (periodStr.isEmpty()) {
			UserUtil.showErr(labP+" is emptry!");
			return;
		}
		if (executionStr.isEmpty()) {
			UserUtil.showErr(labE+" is emptry!");
			return;
		}
		if (deadlineStr.isEmpty()) {
			UserUtil.showErr(labD+" is emptry!");
			return;
		}
		
		double period = Double.parseDouble(periodStr);
		double execution = Double.parseDouble(executionStr);
		double deadline = Double.parseDouble(deadlineStr);
		double jitter = 0, offset = 0, cs = 0, 
				delta_rel = 0, delta_sch = 0, delta_cxs = 0, delta_crpmd = 0;
		Task task=new Task(nameStr);
		task.setPeriod(period);
		task.setExecution(execution);
		task.setDeadline(deadline);
		
		if (!jitterStr.isEmpty()) {
			jitter = Double.parseDouble(jitterStr);
			task.setJitter(jitter);
		}
		if (!offsetStr.isEmpty()) {
			offset = Double.parseDouble(offsetStr);
			task.setOffset(offset);
		}
		if (!csStr.isEmpty()) {
			cs = Double.parseDouble(csStr);
			task.setCriticalSection(cs);

		}
		if(!delta_rel_str.isEmpty()){
			delta_rel = Double.parseDouble(delta_rel_str);
			task.setDelta_rel(delta_rel);

		}
		if(!delta_sch_str.isEmpty()){
			delta_sch = Double.parseDouble(delta_sch_str);
			task.setDelta_sch(delta_sch);
		}
		if(!delta_cxs_str.isEmpty()){
			delta_cxs = Double.parseDouble(delta_cxs_str);
			task.setDelta_cxs(delta_cxs);
		}
		if(!delta_crpmd_str.isEmpty()){
			delta_crpmd = Double.parseDouble(delta_crpmd_str);		
			task.setDelta_crpmd(delta_crpmd);
		}
		
		
		if (mode.equals("ADD"))	{
			dialogParent.replyFromAddTaskDialog(task);
		}
		else{
			dialogParent.replyFromEditTaskDialog(task);
		}
		
		this.dispose();
	}
}
