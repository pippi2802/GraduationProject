package edu.penn.rtg.csa.mpr2;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.text.DecimalFormat;

import edu.penn.rtg.common.GlobalVariable;
import edu.penn.rtg.common.Tool;


/**
 * Class XMLWriter4MPR2
 * This class write the computed interface of the components tree into a xml file
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/12/2013 
 *
 */

public class XMLWriter4MPR2 {
	
	private String outputFilename;
	private BufferedWriter outputFile;
	private String resultString; 
	private Component rootComponent;
	private DecimalFormat df;
	
	public XMLWriter4MPR2(String outputFilename, Component rootComponent){
		try{
			this.rootComponent = rootComponent;
			this.outputFilename = outputFilename;
			outputFile = new BufferedWriter(new FileWriter(outputFilename));
			resultString = "";
			df = new DecimalFormat("#.##");
			System.out.println("Open the file " + outputFilename + " to write...");
		}catch(IOException e){
			System.err.println(e.getMessage());
			e.printStackTrace();
		}
		
	}
	
	public void writeComponentInterfaceTree(int sbf_type){
		try{
			String analysisModel = "";
			if(sbf_type == GlobalVariable.MPR_SBF_ARVIND){
				analysisModel = "MPR2";
			}else if(sbf_type == GlobalVariable.MPR_SBF_MENG){
				analysisModel = "MPR2_Meng";
			}else{
				analysisModel = "Unknown";
			}				
			this.writeComponentInterface(this.rootComponent, analysisModel);
			Tool.debug(resultString);
			outputFile.write(resultString);
			outputFile.flush();
			outputFile.close();
		}catch (IOException e){
			System.err.println(e.getMessage());
			e.printStackTrace();
		}
		
	}
	
	private void writeComponentInterface(Component component, String analysisModel){
		resultString = resultString + "<component name=\"" + component.getComponentName() + "\" resource_model=\"" + analysisModel + " model\" >\r\n" +
					"<resource>\r\n" +
						"<model cpus=\"" + component.getmPR2Interface().getM_prime() + "\" period=\"" + df.format(component.getmPR2Interface().getPi()) + "\" execution_time=\"" + df.format(component.getmPR2Interface().getTheta()) + "\"> </model> \r\n" +
					"</resource> \r\n"; 
		//print out the interface tasks by iteration.
		resultString += "<processed_task> \r\n";
		for(int i=0; !component.getInterfaceTaskset().isEmpty() && i<component.getInterfaceTaskset().size();i++){
			Task currentTask = component.getInterfaceTaskset().get(i);
			resultString += "<model period=\"" + df.format(currentTask.getPeriod()) + "\" execution_time=\"" + 
						df.format(currentTask.getExe()) + "\" deadline=\"" + df.format(currentTask.getDeadline()) + "\" > </model> \r\n";
		}
		resultString += "</processed_task> \r\n";
		//recursively print out the child components' interface
		for(int i=0; i<component.getChildComponents().size(); i++){
			writeComponentInterface(component.getChildComponents().get(i), analysisModel);
		}
		resultString += "</component>\r\n";		
	}
	
	public void writeOriginalComponentTree() throws IOException{
		this.writeOriginalComponent(this.rootComponent);
		//System.out.println(resultString);
		outputFile.write(resultString);
		outputFile.flush();
		outputFile.close();
	}
	
	private void writeOriginalComponent(Component component) {
		resultString = resultString + "< component name="+component.getComponentName() + 
				"  scheduling=" + component.getSchedulingPolicy() + "  period=" + component.getmPR2Interface().getPi() + " > \r\n"; 
		for(int i=0; i<component.getChildComponents().size(); i++){
			writeOriginalComponent(component.getChildComponents().get(i));
		}
		for(int i=0; i<component.getTaskset().size(); i++){
			Task task = component.getTaskset().get(i);
			this.writeOriginalTask(task);
		}
		
		resultString = resultString + "</component> \r\n" ;	

	}
	
	private void writeOriginalTask(Task task){
		resultString = resultString + "< task name=" + task.getName() + " p=" + task.getPeriod() + 
				" d=" + task.getDeadline() + " e=" + task.getExe() + " delta_rel=" + task.getDelta_rel() +
				" delta_sch=" + task.getDelta_sch() + " delta_cxs=" + task.getDelta_cxs() + 
				" delta_crpmd=" + task.getDelta_crpmd() + "/> \r\n"; 
	}
 
	/**
	 * @param args
	 * @throws IOException 
	 */
	public static void main(String[] args) {
		// TODO Auto-generated method stub
		try{
			XMLInterpreter4MPR2 xmlInputParse = new XMLInterpreter4MPR2("CAMPR-input.xml");		
			xmlInputParse.parseFile();
			Component rootComponent = xmlInputParse.getRootComponent();
			XMLWriter4MPR2 xmlOutputOriginalComponentTree = new XMLWriter4MPR2("CAMPR-component-output.xml", rootComponent);
			XMLWriter4MPR2 xmlOutputInterfaceTree = new XMLWriter4MPR2("CAMPR-interface-output.xml", rootComponent);
			
			xmlOutputOriginalComponentTree.writeOriginalComponentTree();
			xmlOutputInterfaceTree.writeComponentInterfaceTree(GlobalVariable.MPR_SBF_ARVIND);
		}catch (Exception e){
			System.err.println(e.getMessage());
			e.printStackTrace();
		}
		
		

	}

}
