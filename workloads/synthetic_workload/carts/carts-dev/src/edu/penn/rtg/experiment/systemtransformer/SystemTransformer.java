package edu.penn.rtg.experiment.systemtransformer;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.text.DecimalFormat;
import java.util.Random;
import java.util.Vector;

import edu.penn.rtg.common.Tool;
import edu.penn.rtg.csa.cadmpr.Component;
import edu.penn.rtg.csa.cadmpr.XMLInterpreter4CADMPR;
import edu.penn.rtg.csa.cadmpr.Task;

public class SystemTransformer {

	
	public SystemTransformer(String inputFilename){
		XMLInterpreter4CADMPR xmlInterpreter = new XMLInterpreter4CADMPR(inputFilename); //4 is short for "for"
		xmlInterpreter.parseFile();
		xmlInterpreter.getRootComponent();
	}
	
	public static DecimalFormat folderDF = new DecimalFormat("#.###");
	public static DecimalFormat fileDF = new DecimalFormat("#.###");
	public static DecimalFormat df = new DecimalFormat("#.###");
	
	public static double OHRATIO_MAX = 0.5;
	public static double OHRATIO_MIN = 0.0;
	
	public static int rootComponentPeriod = 32;
	
	public static Random randomGenerator = new Random(0);
	
	public static double getRandom(){
		double x = randomGenerator.nextDouble();//generate a real number uniformly distributed between 0 and 1.
		return x;
	}
	

	public static void modifyCostOfOverhead(Component component, double ohRatio){
		if(component.getChildComponents() == null || component.getChildComponents().isEmpty()){ //leaf component
			Vector<Task> taskset = component.getTaskset();
			if(taskset == null || taskset.isEmpty()){
				return; //no task to change
			}
			for(int i = 0; i < taskset.size(); i++){
				Task task = taskset.get(i);
				Double delta_crpmd_new = task.getExe() * ohRatio;
				task.setDelta_crpmd(delta_crpmd_new);
			}
		}else{
			for(int i=0; i < component.getChildComponents().size(); i++){
				Component childComponent = component.getChildComponents().get(i);
				modifyCostOfOverhead(childComponent, ohRatio);
			}	
		}
	}
	
	public static void setDifferentCostOfOverhead(Component component){
		if(component.getChildComponents() == null || component.getChildComponents().isEmpty()){ //leaf component
			Vector<Task> taskset = component.getTaskset();
			if(taskset == null || taskset.isEmpty()){
				return; //no task to change
			}
			for(int i = 0; i < taskset.size(); i++){
				Task task = taskset.get(i);
				Double delta_crpmd_new = task.getExe() * ( getRandom() * (OHRATIO_MAX - OHRATIO_MIN) );
				task.setDelta_crpmd(delta_crpmd_new);
			}
		}else{
			for(int i=0; i < component.getChildComponents().size(); i++){
				Component childComponent = component.getChildComponents().get(i);
				setDifferentCostOfOverhead(childComponent);
			}	
		}
	}

	public static void varyCostOfOverhead(String rootPath, double tasksetUtil, double ohRatioMin, double ohRatioStep,
			double ohRatioMax, int tasksetNumPerOhRatio){
		
		String topFolder = rootPath + "/" + fileDF.format(ohRatioMin) + "-" + fileDF.format(ohRatioStep) + "-" + fileDF.format(ohRatioMax) + "-" + tasksetNumPerOhRatio;
		boolean isFolderCreated = (new File(topFolder)).mkdirs();
		if(!isFolderCreated){System.err.println("Create the folder" + topFolder + "for xml files fails!");}
		for(double ohRatio = ohRatioMin; ohRatio < ohRatioMax; ohRatio += ohRatioStep){
			//create the folder for this ohRatio output
			isFolderCreated = (new File(topFolder + "/" + folderDF.format(ohRatio))).mkdirs();
			if(!isFolderCreated){System.err.println("Create the folder for xml files fails!");}
			for(int tasksetIndex = 0; tasksetIndex < tasksetNumPerOhRatio; tasksetIndex++){
				String inputFilename = rootPath + "/" + "rawData" + "/" + tasksetIndex + "-" + fileDF.format(tasksetUtil) + "-in.xml";
				String outputFilename = topFolder + "/" + fileDF.format(ohRatio) + "/" 
						+ tasksetIndex + "-" + fileDF.format(ohRatio) + "-in.xml";
				
				XMLInterpreter4CADMPR xmlInterpreter = new XMLInterpreter4CADMPR(inputFilename); //4 is short for "for"
				xmlInterpreter.parseFile();
				Component rootComponent = xmlInterpreter.getRootComponent();
				
				modifyCostOfOverhead(rootComponent, ohRatio);
				
				writeXML(outputFilename, rootComponent);
			}
		}
	}
	
	public static void setDifferentCostOfOverheadForAllTasksets(String rootPath, double utilMin, 
			double utilStep, double utilMax, int tasksetNumPerUtil){
		
		
		String topFolder = rootPath + "/" + fileDF.format(utilMin) + "-" + fileDF.format(utilStep) + "-" 
			+ fileDF.format(utilMax) + "-" + tasksetNumPerUtil;
		boolean isFolderCreated = (new File(topFolder)).mkdirs();
		if(!isFolderCreated){System.err.println("Create the folder" + topFolder + "for xml files fails!");}
		for(double util = utilMin; util < utilMax; util+= utilStep){
			isFolderCreated = (new File(topFolder + "/" + folderDF.format(util))).mkdirs();
			if(!isFolderCreated){System.err.println("Create the folder for xml files fails!");}
			for(int tasksetIndex = 0; tasksetIndex < tasksetNumPerUtil; tasksetIndex++){
				String inputFilename = rootPath + "/" + "rawData" + "/" + folderDF.format(util) + "/" + tasksetIndex + "-" + fileDF.format(util) + "-in.xml";
				String outputFilename = topFolder + "/" + folderDF.format(util) + "/"  
						+ tasksetIndex + "-" + fileDF.format(util) + "-in.xml";			
				
				XMLInterpreter4CADMPR xmlInterpreter = new XMLInterpreter4CADMPR(inputFilename); //4 is short for "for"
				xmlInterpreter.parseFile();
				Component rootComponent = xmlInterpreter.getRootComponent();
				
				setDifferentCostOfOverhead(rootComponent);
				
				writeXML(outputFilename, rootComponent);
			}
		}
		
	}
	
	public static void putTasksIntoOneComponnet(String rootPath, double utilMin, double utilStep, double utilMax, int tasksetNumPerUtil){
		String topFolderIn = rootPath + "/effect-taskset-util=(0.10-0.20-24.00)" + "/" + fileDF.format(utilMin) + "-" + fileDF.format(utilStep) + "-" 
				+ fileDF.format(utilMax) + "-" + tasksetNumPerUtil;
		String topFolderOut = rootPath + "/one-component-taskset-util=(0.10-0.20-24.00)-period=" + rootComponentPeriod + "/" + fileDF.format(utilMin) + "-" + fileDF.format(utilStep) + "-" 
				+ fileDF.format(utilMax) + "-" + tasksetNumPerUtil;
			boolean isFolderCreated = (new File(topFolderOut)).mkdirs();
			if(!isFolderCreated){System.err.println("Create the folder" + topFolderOut + "for xml files fails!");}
			for(double util = utilMin; util < utilMax; util+= utilStep){
				isFolderCreated = (new File(topFolderOut + "/" + folderDF.format(util))).mkdirs();
				if(!isFolderCreated){System.err.println("Create the folder for xml files fails!");}
				for(int tasksetIndex = 0; tasksetIndex < tasksetNumPerUtil; tasksetIndex++){
					String inputFilename = topFolderIn + "/" + folderDF.format(util) + "/" + tasksetIndex + "-" + fileDF.format(util) + "-in.xml";
					String outputFilename = topFolderOut + "/" + folderDF.format(util) + "/"  
							+ tasksetIndex + "-" + fileDF.format(util) + "-in.xml";			
					
					XMLInterpreter4CADMPR xmlInterpreter = new XMLInterpreter4CADMPR(inputFilename); //4 is short for "for"
					xmlInterpreter.parseFile();
					Component rootComponent = xmlInterpreter.getRootComponent();
					
					writeXML2OneComponent(outputFilename, rootComponent);
				}
			}
	}
	
	public static void main(String[] args) {
		// TODO Auto-generated method stub
		folderDF.setMaximumFractionDigits(2);
		folderDF.setMinimumFractionDigits(2);
		fileDF.setMaximumFractionDigits(2);
		fileDF.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		df.setMinimumFractionDigits(2);
		
		String root = ".";
		root = args[0];
		
		String rootPath_EffectOfOhCost = root + "/workspace-rtsj/effect-costOfCacheOh/4.90";
		varyCostOfOverhead(rootPath_EffectOfOhCost, 4.90, 0.00, 0.01, 0.10, 25);
		
		String rootPath_EffectOfDifferentOh = root + "/workspace-rtsj/effect-differentCostOfCacheOh-ohRatio(0,0.1)";
		setDifferentCostOfOverheadForAllTasksets(rootPath_EffectOfDifferentOh, 0.10, 0.20, 5.00, 25);
		
		String rootPath_oneComponent = root + "/workspace-rtsj";
		for(double util_max=24.00; util_max < 24.03; util_max+=0.01){
	//		putTasksIntoOneComponnet(rootPath_oneComponent, 0.10, 0.20, util_max, 25);

		}
		
	}
	
	
	/**
	 * Only work for two level! For RT-Xen
	 * @param outputFilename
	 * @param rootComponent
	 */
	public static void writeXML(String outputFilename, Component rootComponent){
		String str = "";
		
		if(rootComponent == null){
			System.err.println("not valid rootComponent Exit(1)!");
			System.exit(1);
		}
		
		str += "<system os_scheduler=\"gEDF\" period=\"" + rootComponent.getdMPRInterface().getPi() +  "\"> \r\n";
		
		for(int i=0; i<rootComponent.getChildComponents().size(); i++){
			Component childComponent = rootComponent.getChildComponents().get(i);
			str += "\t<component name=\"C" + i + "\" scheduler=\"gEDF\" period=\""+df.format(childComponent.getdMPRInterface().getPi())+"\"> \r\n";
			for(int j=0; j<childComponent.getTaskset().size(); j++){
				Task task = childComponent.getTaskset().get(j);
				
				str+= "\t\t <task name=\"T" + task.getName() + "\" p=\"" + df.format(task.getPeriod()) + "\" d=\"" + df.format(task.getDeadline()) + 
						"\" e=\"" + df.format(task.getExe()) + "\" " + "delta_rel=\"" + df.format(task.getDelta_rel()) + "\" delta_sch=\"" + df.format(task.getDelta_sch()) + 
						"\" delta_cxs=\"" + df.format(task.getDelta_cxs()) + "\" delta_crpmd=\"" + df.format(task.getDelta_crpmd()) + "\" > </task>\r\n";
			}
			
			str += "\t</component>\r\n";
		}
		str += "</system>\r\n";
		
		try{
			
			BufferedWriter output_xmlFile = new BufferedWriter(new FileWriter(outputFilename,false));
			output_xmlFile.write(str);
			output_xmlFile.flush();
			Tool.debug(str);
			output_xmlFile.close();
		}catch (IOException e){
			System.err.println("GenerateTaskset: open output_xmlFile fails. file name: " + outputFilename + "\r\n");
			Tool.write2log("GenerateTaskset: open output_xmlFile fails. file name: " + outputFilename + "\r\n");
		}
	}
	
	public static void writeXML2OneComponent(String outputFilename, Component rootComponent){
		String str = "";
		
		if(rootComponent == null){
			System.err.println("not valid rootComponent Exit(1)!");
			System.exit(1);
		}
		
		str += "<system os_scheduler=\"gEDF\" period=\"" + rootComponentPeriod +  "\"> \r\n";
		
		for(int i=0; i<rootComponent.getChildComponents().size(); i++){
			Component childComponent = rootComponent.getChildComponents().get(i);
			//str += "\t<component name=\"C" + i + "\" scheduler=\"gEDF\" period=\""+df.format(childComponent.getdMPRInterface().getPi())+"\"> \r\n";
			for(int j=0; j<childComponent.getTaskset().size(); j++){
				Task task = childComponent.getTaskset().get(j);
				
				str+= "\t <task name=\"T" + task.getName() + "\" p=\"" + df.format(task.getPeriod()) + "\" d=\"" + df.format(task.getDeadline()) + 
						"\" e=\"" + df.format(task.getExe()) + "\" " + "delta_rel=\"" + df.format(task.getDelta_rel()) + "\" delta_sch=\"" + df.format(task.getDelta_sch()) + 
						"\" delta_cxs=\"" + df.format(task.getDelta_cxs()) + "\" delta_crpmd=\"" + df.format(task.getDelta_crpmd()) + "\" > </task>\r\n";
			}
			
			//str += "\t</component>\r\n";
		}
		str += "</system>\r\n";
		
		try{
			
			BufferedWriter output_xmlFile = new BufferedWriter(new FileWriter(outputFilename,false));
			output_xmlFile.write(str);
			output_xmlFile.flush();
			Tool.debug(str);
			output_xmlFile.close();
		}catch (IOException e){
			System.err.println("GenerateTaskset: open output_xmlFile fails. file name: " + outputFilename + "\r\n");
			Tool.write2log("GenerateTaskset: open output_xmlFile fails. file name: " + outputFilename + "\r\n");
		}
	}

}
